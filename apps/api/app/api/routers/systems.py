from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID, uuid4
from pydantic import BaseModel
from typing import List

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.users import User, UserRole
from app.models.policies import SystemMapping
from app.models.audit import AuditLog

router = APIRouter()

class SystemMappingCreate(BaseModel):
    system_name: str
    mapped_requirement_ids: List[UUID]

class SystemMappingResponse(BaseModel):
    id: UUID
    org_id: UUID
    system_name: str
    mapped_requirement_ids: List[UUID]

class SystemMappingUpdate(BaseModel):
    system_name: str
    mapped_requirement_ids: List[UUID]

@router.get("", response_model=List[SystemMappingResponse])
async def list_systems(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stmt = select(SystemMapping).where(SystemMapping.org_id == user.org_id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("", response_model=SystemMappingResponse)
async def create_system(
    payload: SystemMappingCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can create system mappings")
        
    system = SystemMapping(
        id=uuid4(),
        org_id=user.org_id,
        system_name=payload.system_name,
        mapped_requirement_ids=payload.mapped_requirement_ids
    )
    db.add(system)
    
    audit_log = AuditLog(
        id=uuid4(),
        org_id=user.org_id,
        actor_id=user.id,
        action="system_mapping.created",
        entity_type="system_mapping",
        entity_id=system.id,
        metadata_payload={"system_name": payload.system_name}
    )
    db.add(audit_log)
    await db.commit()
    await db.refresh(system)
    return system

@router.put("/{id}", response_model=SystemMappingResponse)
async def update_system(
    id: UUID,
    payload: SystemMappingUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can update system mappings")
        
    stmt = select(SystemMapping).where(SystemMapping.id == id, SystemMapping.org_id == user.org_id)
    system = (await db.execute(stmt)).scalar_one_or_none()
    
    if not system:
        raise HTTPException(status_code=404, detail="System not found")
        
    system.system_name = payload.system_name
    system.mapped_requirement_ids = payload.mapped_requirement_ids
    
    audit_log = AuditLog(
        id=uuid4(),
        org_id=user.org_id,
        actor_id=user.id,
        action="system_mapping.updated",
        entity_type="system_mapping",
        entity_id=system.id,
        metadata_payload={"system_name": payload.system_name}
    )
    db.add(audit_log)
    await db.commit()
    await db.refresh(system)
    return system

@router.delete("/{id}")
async def delete_system(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can delete system mappings")
        
    stmt = select(SystemMapping).where(SystemMapping.id == id, SystemMapping.org_id == user.org_id)
    system = (await db.execute(stmt)).scalar_one_or_none()
    
    if not system:
        raise HTTPException(status_code=404, detail="System not found")
        
    await db.delete(system)
    
    audit_log = AuditLog(
        id=uuid4(),
        org_id=user.org_id,
        actor_id=user.id,
        action="system_mapping.deleted",
        entity_type="system_mapping",
        entity_id=id,
        metadata_payload={"system_name": system.system_name}
    )
    db.add(audit_log)
    await db.commit()
    return {"message": "System mapping deleted successfully"}
