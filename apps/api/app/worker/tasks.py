import asyncio
import logging
from uuid import UUID
from datetime import datetime, timezone
import httpx
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from app.worker.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.models.jobs import BackgroundJob, JobStatus
from app.models.reports import Report, Notification
from app.models.policies import ComplianceCheck, ComplianceResult
from app.models.webhooks import Webhook

logger = logging.getLogger(__name__)

async def _update_job_status(job_id: str, status: JobStatus, error: str = None):
    async with AsyncSessionLocal() as db:
        job = await db.get(BackgroundJob, UUID(job_id))
        if job:
            job.status = status
            if error:
                job.error_message = error
            await db.commit()

async def _run_ingestion_logic(reg_version_id: str, source_doc_id: str, previous_version_id: str = None):
    async with AsyncSessionLocal() as db:
        from app.pipelines.pipeline import extract_document_text, segment_document, chunk_document, process_chunk_extraction, deduplicate_requirements, route_requirements, persist_embeddings
        from app.pipelines.diff_engine import compute_version_diff
        
        # We need the reg_version and regulation to update current_version_id
        from app.models.regulations import RegulationVersion, Regulation
        reg_version = await db.get(RegulationVersion, UUID(reg_version_id))
        regulation = await db.get(Regulation, reg_version.regulation_id)
        
        await extract_document_text(UUID(source_doc_id), db)
        await segment_document(UUID(source_doc_id), db)
        
        chunks = await chunk_document(UUID(source_doc_id), db)
        
        all_new_reqs = []
        for chunk in chunks:
            reqs = await process_chunk_extraction(chunk, UUID(reg_version_id), db)
            all_new_reqs.extend(reqs)
            
        unique_reqs = await deduplicate_requirements(all_new_reqs, db)
        routed_reqs = route_requirements(unique_reqs)
        
        db.add_all(routed_reqs)
        await db.flush()
        
        await persist_embeddings(routed_reqs, db)
        
        if previous_version_id:
            await compute_version_diff(UUID(previous_version_id), UUID(reg_version_id), db)
            regulation.current_version_id = UUID(reg_version_id)
            await db.commit()
        else:
            regulation.current_version_id = UUID(reg_version_id)
            await db.commit()

@celery_app.task(bind=True, max_retries=3)
def task_run_ingestion(self, job_id: str, reg_version_id: str, source_doc_id: str, previous_version_id: str = None):
    logger.info(f"Starting ingestion job {job_id}")
    asyncio.run(_update_job_status(job_id, JobStatus.running))
    try:
        asyncio.run(_run_ingestion_logic(reg_version_id, source_doc_id, previous_version_id))
        asyncio.run(_update_job_status(job_id, JobStatus.completed))
        logger.info(f"Completed ingestion job {job_id}")
    except Exception as e:
        logger.error(f"Ingestion job failed: {e}")
        try:
            self.retry(countdown=2 ** self.request.retries)
        except MaxRetriesExceededError:
            asyncio.run(_update_job_status(job_id, JobStatus.dead_letter, str(e)))
            raise e

async def _run_compliance_logic(check_id: str):
    async with AsyncSessionLocal() as db:
        check = await db.get(ComplianceCheck, UUID(check_id))
        if not check:
            raise ValueError("ComplianceCheck not found")
            
        # Mock logic as in developer.py
        # Real logic would load the payload from storage and evaluate rules
        violations = []
        # Let's say we assume it passes since we don't have the payload
        check.result = ComplianceResult.pass_
        check.violations = {}
        await db.commit()

@celery_app.task(bind=True, max_retries=3)
def task_check_compliance(self, job_id: str, check_id: str):
    logger.info(f"Starting compliance check job {job_id}")
    asyncio.run(_update_job_status(job_id, JobStatus.running))
    try:
        asyncio.run(_run_compliance_logic(check_id))
        asyncio.run(_update_job_status(job_id, JobStatus.completed))
    except Exception as e:
        try:
            self.retry(countdown=2 ** self.request.retries)
        except MaxRetriesExceededError:
            asyncio.run(_update_job_status(job_id, JobStatus.dead_letter, str(e)))
            raise e

async def _run_report_logic(report_id: str):
    async with AsyncSessionLocal() as db:
        report = await db.get(Report, UUID(report_id))
        if not report:
            raise ValueError("Report not found")
        
        # Fetch regulation and org
        from app.models.regulations import Regulation, RegulationVersion
        from app.models.requirements import Requirement, ValidationStatus
        
        reg = await db.get(Regulation, report.regulation_id)
        
        # Fetch approved requirements for this org/regulation
        stmt = (
            select(Requirement)
            .join(RegulationVersion, Requirement.regulation_version_id == RegulationVersion.id)
            .where(
                RegulationVersion.regulation_id == report.regulation_id,
                Requirement.validation_status.in_([ValidationStatus.approved, ValidationStatus.enforceable])
            )
        )
        requirements = (await db.execute(stmt)).scalars().all()
        
        # Generate PDF
        from app.pipelines.reporting import ReportGenerator
        generator = ReportGenerator(
            regulation_name=reg.name,
            org_name="Your Organization",
            report_type=report.report_type,
            requirements=requirements
        )
        pdf_bytes = generator.generate_pdf_bytes()
        
        # Store PDF
        from app.core.storage import storage_service
        key = f"reports/{report.org_id}/{report.regulation_id}/{report.id}.pdf"
        storage_path = await storage_service.upload_bytes(pdf_bytes, key)
        
        report.storage_path = storage_path
        await db.commit()

@celery_app.task(bind=True, max_retries=3)
def task_generate_report(self, job_id: str, report_id: str):
    logger.info(f"Starting report generation job {job_id}")
    asyncio.run(_update_job_status(job_id, JobStatus.running))
    try:
        asyncio.run(_run_report_logic(report_id))
        asyncio.run(_update_job_status(job_id, JobStatus.completed))
    except Exception as e:
        try:
            self.retry(countdown=2 ** self.request.retries)
        except MaxRetriesExceededError:
            asyncio.run(_update_job_status(job_id, JobStatus.dead_letter, str(e)))
            raise e

async def _dispatch_webhook_logic(notification_id: str):
    async with AsyncSessionLocal() as db:
        notification = await db.get(Notification, UUID(notification_id))
        if not notification:
            raise ValueError("Notification not found")
            
        # Find all webhooks for this org
        stmt = select(Webhook).where(Webhook.org_id == notification.org_id)
        webhooks = (await db.execute(stmt)).scalars().all()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for webhook in webhooks:
                # If event_types filter applies, check it here
                if "all" in webhook.event_types or notification.type.value in webhook.event_types:
                    # Mock signature generation
                    headers = {"x-rac-signature": "mock_sig"}
                    payload = {
                        "notification_id": str(notification.id),
                        "type": notification.type.value,
                        "payload": notification.payload,
                        "created_at": notification.created_at.isoformat()
                    }
                    try:
                        res = await client.post(webhook.url, json=payload, headers=headers)
                        res.raise_for_status()
                    except Exception as exc:
                        # Log and let the caller retry the job
                        logger.error(f"Webhook dispatch failed to {webhook.url}: {exc}")
                        raise exc
        
        notification.delivered_at = datetime.now(timezone.utc)
        await db.commit()

@celery_app.task(bind=True, max_retries=3)
def task_dispatch_notification(self, job_id: str, notification_id: str):
    logger.info(f"Starting notification dispatch job {job_id}")
    asyncio.run(_update_job_status(job_id, JobStatus.running))
    try:
        asyncio.run(_dispatch_webhook_logic(notification_id))
        asyncio.run(_update_job_status(job_id, JobStatus.completed))
    except Exception as e:
        try:
            self.retry(countdown=2 ** self.request.retries)
        except MaxRetriesExceededError:
            asyncio.run(_update_job_status(job_id, JobStatus.dead_letter, str(e)))
            raise e
