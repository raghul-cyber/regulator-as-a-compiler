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

class FullRequirementResponse(BaseModel):
    id: UUID
    regulation_version_id: UUID
    section_id: Optional[UUID] = None
    type: str
    title: str
    description: str
    conditions: dict
    actions: dict
    severity: str
    evidence_required: dict
    references: dict
    confidence_score: float
    validation_status: str
    rejection_reason: Optional[str] = None
    reviewed_by_user_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    search_score: Optional[float] = None
    similarity_score: Optional[float] = None

@router.get("/{id}/similar", response_model=list[FullRequirementResponse])
async def get_similar_requirements(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    from app.models.requirements import RequirementEmbedding
    
    stmt_emb = select(RequirementEmbedding).where(RequirementEmbedding.requirement_id == id)
    target_emb = (await db.execute(stmt_emb)).scalar_one_or_none()
    
    if not target_emb or target_emb.embedding is None:
        return []
        
    stmt = select(Requirement, RequirementEmbedding.embedding)\
        .join(RequirementEmbedding, Requirement.id == RequirementEmbedding.requirement_id)\
        .where(Requirement.id != id)
        
    result = await db.execute(stmt)
    candidates = result.all()
    
    similar = []
    for req, emb in candidates:
        if emb is not None:
            try:
                dot = sum(a * b for a, b in zip(target_emb.embedding, emb))
                sim = max(0.0, float(dot))
                similar.append((req, sim))
            except Exception:
                pass
                
    similar.sort(key=lambda x: x[1], reverse=True)
    top_5 = similar[:5]
    
    return [
        FullRequirementResponse(
            id=req.id,
            regulation_version_id=req.regulation_version_id,
            section_id=req.section_id,
            type=req.type.value if hasattr(req.type, 'value') else str(req.type),
            title=req.title,
            description=req.description,
            conditions=req.conditions,
            actions=req.actions,
            severity=req.severity.value if hasattr(req.severity, 'value') else str(req.severity),
            evidence_required=req.evidence_required,
            references=req.references,
            confidence_score=float(req.confidence_score),
            validation_status=req.validation_status.value if hasattr(req.validation_status, 'value') else str(req.validation_status),
            rejection_reason=req.rejection_reason,
            reviewed_by_user_id=req.reviewed_by_user_id,
            reviewed_at=req.reviewed_at,
            similarity_score=round(sim, 4)
        )
        for req, sim in top_5
    ]

@router.get("", response_model=list[FullRequirementResponse])
async def search_all_requirements(
    search: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    from app.models.documents import DocumentSection
    from app.models.requirements import RequirementEmbedding
    
    query = select(Requirement, DocumentSection.raw_text, RequirementEmbedding.embedding)\
        .outerjoin(DocumentSection, Requirement.section_id == DocumentSection.id)\
        .outerjoin(RequirementEmbedding, Requirement.id == RequirementEmbedding.requirement_id)
        
    result = await db.execute(query)
    rows = result.all()
    
    if search:
        search_vec = None
        try:
            from app.pipelines.dedup import generate_embedding
            search_vec = await generate_embedding(search, db)
        except Exception:
            search_vec = None
            
        search_lower = search.lower().strip()
        search_terms = search_lower.split()
        scored_items = []
        
        for req, sec_text, emb in rows:
            full_text = f"{req.title} {req.description} {sec_text or ''}".lower()
            matches = sum(full_text.count(term) for term in search_terms)
            kw_score = min(1.0, matches * 0.15) if matches > 0 else 0.0
            if search_lower in full_text:
                kw_score = min(1.0, kw_score + 0.3)
            sem_score = 0.0
            if search_vec and emb is not None:
                try:
                    dot = sum(a * b for a, b in zip(search_vec, emb))
                    sem_score = max(0.0, float(dot))
                except Exception:
                    sem_score = 0.0
            combined_score = (kw_score * 2.0) + sem_score
            if kw_score > 0.0 or sem_score > 0.25:
                req.search_score = round(combined_score, 4)
                scored_items.append((req, combined_score))
                
        scored_items.sort(key=lambda x: x[1], reverse=True)
        requirements = [x[0] for x in scored_items][:limit]
    else:
        requirements = [row[0] for row in rows][:limit]
        requirements.sort(key=lambda r: r.created_at, reverse=True)
        
    return [
        FullRequirementResponse(
            id=req.id,
            regulation_version_id=req.regulation_version_id,
            section_id=req.section_id,
            type=req.type.value if hasattr(req.type, 'value') else str(req.type),
            title=req.title,
            description=req.description,
            conditions=req.conditions,
            actions=req.actions,
            severity=req.severity.value if hasattr(req.severity, 'value') else str(req.severity),
            evidence_required=req.evidence_required,
            references=req.references,
            confidence_score=float(req.confidence_score),
            validation_status=req.validation_status.value if hasattr(req.validation_status, 'value') else str(req.validation_status),
            rejection_reason=req.rejection_reason,
            reviewed_by_user_id=req.reviewed_by_user_id,
            reviewed_at=req.reviewed_at,
            search_score=getattr(req, 'search_score', None)
        )
        for req in requirements
    ]
