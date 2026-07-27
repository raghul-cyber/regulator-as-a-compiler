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

    # Update regulation's current version if it's the first one
    if not regulation.current_version_id:
        regulation.current_version_id = reg_version.id

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

    # --- Phase 5: LLM Extraction, Dedup, Validation ---
    try:
        await extract_document_text(source_doc_id, db)
        await segment_document(source_doc_id, db)
        
        # 1. Chunking
        chunks = await chunk_document(source_doc_id, db)
        
        # 2. LLM Extraction
        all_new_reqs = []
        for chunk in chunks:
            reqs = await process_chunk_extraction(chunk, reg_version.id, db)
            all_new_reqs.extend(reqs)
            
        # 3. Deduplication
        unique_reqs = await deduplicate_requirements(all_new_reqs, db)
        
        # 4. Validation Routing
        routed_reqs = route_requirements(unique_reqs)
        
        # Persist requirements
        db.add_all(routed_reqs)
        await db.flush()  # Flush so requirements get IDs
        
        # 5. Persist Embeddings
        await persist_embeddings(routed_reqs, db)
        
        # Update RegulationVersion status-like label
        reg_version.version_label = "Processed"
        await db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Pipeline failed for {source_doc_id}: {e}")
        reg_version.version_label = "Failed Pipeline"
        await db.commit()

    return RegulationUploadResponse(
        regulation_id=regulation.id,
        regulation_version_id=reg_version.id,
        job_id="job_placeholder_123"
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
        
    return {
        "id": regulation.id,
        "name": regulation.name,
        "jurisdiction": regulation.jurisdiction,
        "current_version_id": regulation.current_version_id,
        "status": "processing" # hardcoded for Phase 3
    }
