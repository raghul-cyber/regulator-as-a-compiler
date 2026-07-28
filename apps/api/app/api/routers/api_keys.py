import secrets
from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.api_keys import ApiKey
from app.models.users import User, UserRole
from app.models.audit import AuditLog
from app.core.auth import get_current_user, require_role
from app.core.api_keys import hash_api_key

router = APIRouter()

class ApiKeyCreate(BaseModel):
    scopes: list[str] = Field(..., description="e.g. read-only, check-compliance, admin")

class ApiKeyCreateResponse(BaseModel):
    id: UUID
    raw_key: str
    scopes: list[str]
    created_at: datetime

class ApiKeyResponse(BaseModel):
    id: UUID
    scopes: list[str]
    created_at: datetime
    revoked_at: datetime | None

@router.post("", response_model=ApiKeyCreateResponse)
async def create_api_key(
    req: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.developer))
):
    valid_scopes = {"read-only", "check-compliance", "admin"}
    for scope in req.scopes:
        if scope not in valid_scopes:
            raise HTTPException(status_code=400, detail=f"Invalid scope: {scope}")
            
    raw_key = f"sk_live_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(raw_key)
    
    new_key = ApiKey(
        org_id=user.org_id,
        key_hash=key_hash,
        scopes=req.scopes
    )
    db.add(new_key)
    await db.flush()
    
    audit_log = AuditLog(
        id=uuid4(),
        org_id=user.org_id,
        actor_id=user.id,
        action="api_key.created",
        entity_type="api_key",
        entity_id=new_key.id,
        metadata_payload={"scopes": req.scopes}
    )
    db.add(audit_log)
    await db.commit()
    await db.refresh(new_key)
    
    return ApiKeyCreateResponse(
        id=new_key.id,
        raw_key=raw_key,
        scopes=new_key.scopes,
        created_at=new_key.created_at
    )

@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.developer))
):
    stmt = select(ApiKey).where(ApiKey.org_id == user.org_id)
    result = await db.execute(stmt)
    keys = result.scalars().all()
    
    return [
        ApiKeyResponse(
            id=k.id,
            scopes=k.scopes,
            created_at=k.created_at,
            revoked_at=k.revoked_at
        ) for k in keys
    ]

@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.developer))
):
    stmt = select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == user.org_id)
    result = await db.execute(stmt)
    key = result.scalar_one_or_none()
    
    if not key:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    if key.revoked_at:
        raise HTTPException(status_code=400, detail="API Key is already revoked")
        
    key.revoked_at = datetime.now(timezone.utc)
    
    audit_log = AuditLog(
        id=uuid4(),
        org_id=user.org_id,
        actor_id=user.id,
        action="api_key.revoked",
        entity_type="api_key",
        entity_id=key.id,
        metadata_payload={}
    )
    db.add(audit_log)
    await db.commit()
