from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.users import User, UserRole
from app.models.jobs import BackgroundJob, JobStatus

router = APIRouter()

class JobResponse(BaseModel):
    id: UUID
    job_type: str
    status: JobStatus
    payload: Optional[dict]
    error_message: Optional[str]
    retries: int
    created_at: datetime
    updated_at: datetime

@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stmt = select(BackgroundJob).where(BackgroundJob.id == job_id)
    job = (await db.execute(stmt)).scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return job

@router.get("", response_model=List[JobResponse])
async def list_jobs(
    status_filter: Optional[JobStatus] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can list all jobs")
        
    stmt = select(BackgroundJob)
    if status_filter:
        stmt = stmt.where(BackgroundJob.status == status_filter)
    stmt = stmt.order_by(BackgroundJob.created_at.desc())
    
    jobs = (await db.execute(stmt)).scalars().all()
    return jobs

@router.post("/{job_id}/requeue", response_model=JobResponse)
async def requeue_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can requeue jobs")
        
    job = await db.get(BackgroundJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.status != JobStatus.dead_letter and job.status != JobStatus.failed:
        raise HTTPException(status_code=400, detail="Only failed or dead_letter jobs can be requeued")
        
    job.status = JobStatus.pending
    job.error_message = None
    job.retries = 0
    await db.commit()
    await db.refresh(job)
    
    # Re-dispatch based on job_type
    if job.job_type == "ingestion":
        from app.worker.tasks import task_run_ingestion
        payload = job.payload or {}
        task_run_ingestion.apply_async(
            args=[str(job.id), payload.get("reg_version_id"), payload.get("source_doc_id"), payload.get("previous_version_id")],
            queue="ingestion"
        )
    elif job.job_type == "compliance":
        from app.worker.tasks import task_check_compliance
        payload = job.payload or {}
        task_check_compliance.apply_async(
            args=[str(job.id), payload.get("check_id")],
            queue="compliance"
        )
    elif job.job_type == "report":
        from app.worker.tasks import task_generate_report
        payload = job.payload or {}
        task_generate_report.apply_async(
            args=[str(job.id), payload.get("report_id")],
            queue="reports"
        )
    elif job.job_type == "notification":
        from app.worker.tasks import task_dispatch_notification
        payload = job.payload or {}
        task_dispatch_notification.apply_async(
            args=[str(job.id), payload.get("notification_id")],
            queue="notifications"
        )
        
    return job
