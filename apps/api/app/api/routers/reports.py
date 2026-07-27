import jwt
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.users import User
from app.models.requirements import Requirement, ValidationStatus
from app.models.regulations import RegulationVersion, Regulation
from app.models.reports import Report, ReportType
from app.pipelines.reporting import ReportGenerator
from app.core.storage import storage_service

router = APIRouter(prefix="/api/v1", tags=["reports"])

JWT_SECRET = "super_secret_for_signed_urls_phase8"

class ReportGenerateRequest(BaseModel):
    regulation_id: UUID
    report_type: ReportType

class ReportResponse(BaseModel):
    id: UUID
    regulation_id: UUID
    report_type: ReportType
    generated_at: datetime
    download_url: str

@router.get("/regulations/{regulation_id}/export")
async def export_requirements_json(
    regulation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Raw JSON export matching PRD Section 11 Data Model."""
    stmt = (
        select(Requirement)
        .join(RegulationVersion, Requirement.regulation_version_id == RegulationVersion.id)
        .where(
            RegulationVersion.regulation_id == regulation_id,
            Requirement.validation_status.in_([ValidationStatus.approved, ValidationStatus.enforceable])
        )
    )
    results = (await db.execute(stmt)).scalars().all()
    
    # Manually serialize to match section 11 exactly
    export_data = []
    for req in results:
        export_data.append({
            "id": str(req.id),
            "regulation_version_id": str(req.regulation_version_id),
            "section_id": str(req.section_id) if req.section_id else None,
            "type": req.type.value,
            "title": req.title,
            "description": req.description,
            "conditions": req.conditions,
            "actions": req.actions,
            "severity": req.severity.value,
            "evidence_required": req.evidence_required,
            "references": req.references,
            "confidence_score": req.confidence_score,
            "validation_status": req.validation_status.value
        })
    return export_data

@router.post("/reports", response_model=ReportResponse)
async def generate_report(
    payload: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Fetch regulation
    reg = (await db.execute(select(Regulation).where(Regulation.id == payload.regulation_id))).scalar_one_or_none()
    if not reg:
        raise HTTPException(status_code=404, detail="Regulation not found")

    report_id = uuid4()
    report = Report(
        id=report_id,
        org_id=user.org_id,
        regulation_id=payload.regulation_id,
        report_type=payload.report_type,
        storage_path="", # Will be set by worker
        generated_at=datetime.now(timezone.utc),
        metadata_payload={"status": "pending"}
    )
    db.add(report)
    await db.commit()
    
    # Create BackgroundJob
    from app.models.jobs import BackgroundJob, JobStatus
    job = BackgroundJob(
        job_type="report",
        status=JobStatus.pending,
        payload={"report_id": str(report.id)}
    )
    db.add(job)
    await db.commit()
    
    # Enqueue task
    from app.worker.tasks import task_generate_report
    task_generate_report.apply_async(
        args=[str(job.id), str(report.id)],
        queue="reports"
    )
    
    # Generate signed URL
    exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    token = jwt.encode({"report_id": str(report.id), "org_id": str(user.org_id), "exp": exp}, JWT_SECRET, algorithm="HS256")
    
    return ReportResponse(
        id=report.id,
        regulation_id=report.regulation_id,
        report_type=report.report_type,
        generated_at=report.generated_at,
        download_url=f"/api/v1/reports/download?token={token}"
    )

@router.get("/reports/download")
async def download_report(token: str, db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Download URL has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid download signature")
        
    report_id = payload.get("report_id")
    org_id = payload.get("org_id")
    
    stmt = select(Report).where(Report.id == UUID(report_id))
    report = (await db.execute(stmt)).scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    # Enforce org scoping even on signed URL
    if str(report.org_id) != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this organization's report")
        
    pdf_bytes = await storage_service.get_file(report.storage_path)
    
    import io
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={report.report_type.value}.pdf"})


@router.get("/reports/{regulation_id}", response_model=List[ReportResponse])
async def list_reports(
    regulation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stmt = select(Report).where(Report.regulation_id == regulation_id, Report.org_id == user.org_id)
    reports = (await db.execute(stmt)).scalars().all()
    
    resp = []
    for r in reports:
        exp = datetime.now(timezone.utc) + timedelta(minutes=15)
        token = jwt.encode({"report_id": str(r.id), "org_id": str(user.org_id), "exp": exp}, JWT_SECRET, algorithm="HS256")
        resp.append(ReportResponse(
            id=r.id,
            regulation_id=r.regulation_id,
            report_type=r.report_type,
            generated_at=r.generated_at,
            download_url=f"/api/v1/reports/download?token={token}"
        ))
    return resp

