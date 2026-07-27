from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.users import User, UserRole
from app.models.requirements import Requirement, ValidationStatus
from app.models.audit import AuditLog

router = APIRouter(prefix="/api/requirements", tags=["requirements"])

class RequirementUpdateRequest(BaseModel):
    validation_status: Optional[ValidationStatus] = None
    title: Optional[str] = None
    description: Optional[str] = None
    rejection_reason: Optional[str] = None

class RequirementResponse(BaseModel):
    id: UUID
    validation_status: ValidationStatus
    rejection_reason: Optional[str] = None
    reviewed_by_user_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None

@router.patch("/{id}", response_model=RequirementResponse)
async def update_requirement(
    id: UUID,
    payload: RequirementUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stmt = select(Requirement).where(Requirement.id == id)
    result = await db.execute(stmt)
    req = result.scalar_one_or_none()
    
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
        
    old_status = req.validation_status
    
    if payload.title is not None:
        req.title = payload.title
    if payload.description is not None:
        req.description = payload.description
        
    # Handle status transitions
    if payload.validation_status and payload.validation_status != req.validation_status:
        # Check permissions for approval/rejection
        if payload.validation_status in (ValidationStatus.approved, ValidationStatus.enforceable):
            if user.role not in (UserRole.admin, UserRole.compliance_officer, UserRole.legal_counsel):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="Insufficient permissions to approve requirements"
                )
        
        # If rejecting (transitioning back to draft from pending_review)
        if payload.validation_status == ValidationStatus.draft and old_status != ValidationStatus.draft:
            if not payload.rejection_reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Rejection requires a reason"
                )
            req.rejection_reason = payload.rejection_reason
        elif payload.validation_status != ValidationStatus.draft:
            # Clear rejection reason if moving forward
            req.rejection_reason = None
            
        req.validation_status = payload.validation_status
        req.reviewed_by_user_id = user.id
        req.reviewed_at = datetime.now(timezone.utc)
        
        # Create audit log
        audit_log = AuditLog(
            id=uuid4(),
            org_id=user.org_id,
            actor_id=user.id,
            action="requirement.status_changed",
            entity_type="requirement",
            entity_id=req.id,
            metadata_payload={
                "old_status": old_status.value,
                "new_status": req.validation_status.value,
                "rejection_reason": req.rejection_reason
            }
        )
        db.add(audit_log)
        
    await db.commit()
    await db.refresh(req)
    
    return RequirementResponse(
        id=req.id,
        validation_status=req.validation_status,
        rejection_reason=req.rejection_reason,
        reviewed_by_user_id=req.reviewed_by_user_id,
        reviewed_at=req.reviewed_at
    )
