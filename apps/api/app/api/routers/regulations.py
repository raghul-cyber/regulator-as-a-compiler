from uuid import UUID, uuid4
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.auth import require_role, get_current_user
from app.db.session import get_db
from app.db.repository import BaseRepository
from app.models.users import User, UserRole
from app.models.regulations import Regulation, RegulationVersion
from app.models.documents import SourceDocument, FileType
from app.models.audit import AuditLog
from app.core.storage import storage_service
from app.pipelines.extraction import extract_document_text
from app.pipelines.segmentation import segment_document
from app.pipelines.chunking import chunk_document
from app.pipelines.llm_extraction import process_chunk_extraction
from app.pipelines.dedup import deduplicate_requirements, persist_embeddings
from app.pipelines.validation_routing import route_requirements
from app.pipelines.diff_engine import compute_version_diff
from app.models.requirements import Requirement, RequirementType, Severity, ValidationStatus
from pydantic import Field
from typing import Optional

router = APIRouter(prefix="/api/regulations", tags=["regulations"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

class RegulationUploadResponse(BaseModel):
    regulation_id: UUID
    regulation_version_id: UUID
    job_id: str

@router.post("/upload", response_model=RegulationUploadResponse)
async def upload_regulation(
    jurisdiction: Annotated[str, Form()],
    name: Annotated[str, Form()],
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.compliance_officer))
):
    # 1. Validate file type
    if file.content_type not in ["application/pdf", "text/html"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only PDF or HTML are allowed."
        )

    file_type_enum = FileType.pdf if file.content_type == "application/pdf" else FileType.html

    # Check file size if available via headers, though usually streaming is better.
    # We will assume client also checks size, but we can do a naive check if size is sent.
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds the 50MB limit."
        )

    # 2. Get or create Regulation
    stmt = select(Regulation).where(
        Regulation.name == name,
        Regulation.jurisdiction == jurisdiction
    )
    result = await db.execute(stmt)
    regulation = result.scalar_one_or_none()
    
    if not regulation:
        regulation = Regulation(
            id=uuid4(),
            name=name,
            jurisdiction=jurisdiction,
            source_url="" # Initial upload might not have a URL
        )
        db.add(regulation)
        # Flush to get the regulation ID
        await db.flush()

    # 3. Create RegulationVersion (draft)
    reg_version_id = uuid4()
    reg_version = RegulationVersion(
        id=reg_version_id,
        regulation_id=regulation.id,
        version_label="Draft",
        published_date=date.today(),
        ingested_at=datetime.now(timezone.utc),
        source_document_id=None, # Will update after SourceDocument is created
        diff_summary=None
    )
    db.add(reg_version)
    
    # Flush to guarantee RegulationVersion is inserted first
    await db.flush()
    
    # 4. Stream file to storage
    file_key = f"{regulation.jurisdiction}/{regulation.name}/{reg_version_id}/{file.filename}"
    storage_path = await storage_service.upload_file(file, file_key)

    # 5. Create SourceDocument
    source_doc_id = uuid4()
    source_document = SourceDocument(
        id=source_doc_id,
        regulation_version_id=reg_version_id,
        file_type=file_type_enum,
        storage_path=storage_path,
        raw_text="",
        ocr_used=False,
        page_count=0 # Placeholder until extraction runs
    )
    db.add(source_document)

    # Flush so SourceDocument is created before we link it back
    await db.flush()

    # Now link it back
    reg_version.source_document_id = source_doc_id

    previous_version_id = None
    # Update regulation's current version if it's the first one
    if not regulation.current_version_id:
        regulation.current_version_id = reg_version.id
    else:
        previous_version_id = regulation.current_version_id
        

    # 6. Audit Log
    audit_log = AuditLog(
        id=uuid4(),
        org_id=user.org_id,
        actor_id=user.id,
        action="regulation.uploaded",
        entity_type="regulation",
        entity_id=regulation.id,
        metadata_payload={
            "jurisdiction": jurisdiction,
            "name": name,
            "file_name": file.filename,
            "file_type": file_type_enum.value,
            "version_id": str(reg_version.id)
        }
    )
    db.add(audit_log)

    await db.commit()

    # --- Phase 12: Async Ingestion via Celery ---
    from app.models.jobs import BackgroundJob, JobStatus
    
    # Create BackgroundJob
    job = BackgroundJob(
        job_type="ingestion",
        status=JobStatus.pending,
        payload={
            "reg_version_id": str(reg_version.id),
            "source_doc_id": str(source_doc_id),
            "previous_version_id": str(previous_version_id) if previous_version_id else None
        }
    )
    db.add(job)
    await db.commit()
    
    # Dispatch task
    from app.worker.tasks import task_run_ingestion
    task_run_ingestion.apply_async(
        args=[str(job.id), str(reg_version.id), str(source_doc_id), str(previous_version_id) if previous_version_id else None],
        queue="ingestion"
    )

    return RegulationUploadResponse(
        regulation_id=regulation.id,
        regulation_version_id=reg_version.id,
        job_id=str(job.id)
    )

@router.get("/{id}")
async def get_regulation(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # In a full multi-tenant setup, regulations might be shared or org-scoped. 
    # For now, we just fetch it.
    stmt = select(Regulation).where(Regulation.id == id)
    result = await db.execute(stmt)
    regulation = result.scalar_one_or_none()
    
    if not regulation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulation not found")
        
    status_label = "unknown"
    if regulation.current_version_id:
        stmt_ver = select(RegulationVersion).where(RegulationVersion.id == regulation.current_version_id)
        ver = (await db.execute(stmt_ver)).scalar_one_or_none()
        if ver:
            status_label = ver.version_label

    return {
        "id": regulation.id,
        "name": regulation.name,
        "jurisdiction": regulation.jurisdiction,
        "current_version_id": regulation.current_version_id,
        "status": status_label
    }

class RequirementResponse(BaseModel):
    id: UUID
    regulation_version_id: UUID
    section_id: Optional[UUID] = None
    type: RequirementType
    title: str
    description: str
    conditions: dict
    actions: dict
    severity: Severity
    evidence_required: dict
    references: dict
    confidence_score: float
    validation_status: ValidationStatus
    rejection_reason: Optional[str] = None
    reviewed_by_user_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    search_score: Optional[float] = None

class PaginatedRequirementsResponse(BaseModel):
    items: list[RequirementResponse]
    total: int
    page: int
    size: int

@router.get("/{id}/requirements", response_model=PaginatedRequirementsResponse)
async def get_regulation_requirements(
    id: UUID,
    type: Optional[RequirementType] = None,
    severity: Optional[Severity] = None,
    status: Optional[ValidationStatus] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    from sqlalchemy import func, text
    from app.models.documents import DocumentSection
    from app.models.requirements import RequirementEmbedding
    
    # Get the regulation's current version
    stmt_reg = select(Regulation).where(Regulation.id == id)
    reg = (await db.execute(stmt_reg)).scalar_one_or_none()
    
    if not reg or not reg.current_version_id:
        raise HTTPException(status_code=404, detail="Regulation or version not found")
        
    query = select(Requirement, DocumentSection.raw_text, RequirementEmbedding.embedding)\
        .outerjoin(DocumentSection, Requirement.section_id == DocumentSection.id)\
        .outerjoin(RequirementEmbedding, Requirement.id == RequirementEmbedding.requirement_id)\
        .where(Requirement.regulation_version_id == reg.current_version_id)
    
    if type:
        query = query.where(Requirement.type == type)
    if severity:
        query = query.where(Requirement.severity == severity)
    if status:
        query = query.where(Requirement.validation_status == status)
        
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
        requirements = [x[0] for x in scored_items]
        total = len(requirements)
        paginated = requirements[(page - 1) * size : page * size]
    else:
        requirements = [row[0] for row in rows]
        requirements.sort(key=lambda r: r.created_at, reverse=True)
        total = len(requirements)
        paginated = requirements[(page - 1) * size : page * size]
    
    return PaginatedRequirementsResponse(
        items=[
            RequirementResponse(
                id=r.id,
                regulation_version_id=r.regulation_version_id,
                section_id=r.section_id,
                type=r.type,
                title=r.title,
                description=r.description,
                conditions=r.conditions,
                actions=r.actions,
                severity=r.severity,
                evidence_required=r.evidence_required,
                references=r.references,
                confidence_score=float(r.confidence_score),
                validation_status=r.validation_status,
                rejection_reason=r.rejection_reason,
                reviewed_by_user_id=r.reviewed_by_user_id,
                reviewed_at=r.reviewed_at,
                search_score=getattr(r, 'search_score', None)
            )
            for r in paginated
        ],
        total=total,
        page=page,
        size=size
    )

from app.models.diffs import RequirementDiff

class DiffResponse(BaseModel):
    added: list[RequirementResponse]
    removed: list[RequirementResponse]
    modified: list[dict] # Contains {"old": RequirementResponse, "new": RequirementResponse}

@router.get("/{id}/diff", response_model=DiffResponse)
async def get_regulation_diff(
    id: UUID,
    from_version: Optional[UUID] = None,
    to_version: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # If to_version is not provided, use current_version
    stmt_reg = select(Regulation).where(Regulation.id == id)
    reg = (await db.execute(stmt_reg)).scalar_one_or_none()
    
    if not reg or not reg.current_version_id:
        raise HTTPException(status_code=404, detail="Regulation or version not found")
        
    target_version_id = to_version or reg.current_version_id
    
    # We query the RequirementDiff for this target_version
    diff_stmt = select(RequirementDiff).where(RequirementDiff.regulation_version_id == target_version_id)
    diffs = (await db.execute(diff_stmt)).scalars().all()
    
    if not diffs:
        return DiffResponse(added=[], removed=[], modified=[])
        
    # Gather IDs to fetch requirements
    req_ids = set()
    for d in diffs:
        if d.old_requirement_id: req_ids.add(d.old_requirement_id)
        if d.new_requirement_id: req_ids.add(d.new_requirement_id)
        
    reqs_stmt = select(Requirement).where(Requirement.id.in_(req_ids))
    reqs_result = (await db.execute(reqs_stmt)).scalars().all()
    reqs_map = {r.id: r for r in reqs_result}
    
    def to_resp(r):
        if not r: return None
        return RequirementResponse(
            id=r.id, regulation_version_id=r.regulation_version_id, section_id=r.section_id, type=r.type,
            title=r.title, description=r.description, conditions=r.conditions, actions=r.actions,
            severity=r.severity, evidence_required=r.evidence_required, references=r.references,
            confidence_score=float(r.confidence_score), validation_status=r.validation_status,
            rejection_reason=r.rejection_reason, reviewed_by_user_id=r.reviewed_by_user_id, reviewed_at=r.reviewed_at,
            search_score=getattr(r, 'search_score', None)
        )

    added = []
    removed = []
    modified = []
    
    for d in diffs:
        if d.status == "added" and d.new_requirement_id in reqs_map:
            added.append(to_resp(reqs_map[d.new_requirement_id]))
        elif d.status == "removed" and d.old_requirement_id in reqs_map:
            removed.append(to_resp(reqs_map[d.old_requirement_id]))
        elif d.status == "modified" and d.old_requirement_id in reqs_map and d.new_requirement_id in reqs_map:
            modified.append({
                "old": to_resp(reqs_map[d.old_requirement_id]),
                "new": to_resp(reqs_map[d.new_requirement_id])
            })
            
    return DiffResponse(added=added, removed=removed, modified=modified)
