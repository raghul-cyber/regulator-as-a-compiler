import asyncio
import httpx
import uuid
import time
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.jobs import BackgroundJob, JobStatus
from app.models.users import User, UserRole
from app.models.reports import Report

async def verify_phase12():
    print("--- Verifying Phase 12: Async Processing & Celery ---")
    
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        # 1. Check if we have an admin user, otherwise create a mock one for testing jobs API
        stmt = select(User).where(User.role == UserRole.admin).limit(1)
        admin = (await db.execute(stmt)).scalar_one_or_none()
        
        if not admin:
            admin_id = uuid.uuid4()
            org_id = uuid.uuid4()
            admin = User(id=admin_id, email="admin_p12@test.com", clerk_id=f"clerk_{admin_id}", org_id=org_id, role=UserRole.admin)
            db.add(admin)
            await db.commit()
            print(f"Created mock admin user: {admin.id}")
            
        org_id = admin.org_id
        
        # We need an API key to test the APIs if we wanted to run them end to end, but we can also just create Jobs directly in the DB to test the worker.
        # But wait, to test the worker end to end, we should hit the real API or just insert a job and let Celery pick it up.
        # Since we modified the routers to dispatch to Celery, we can test that the Celery worker picks up jobs we manually dispatch, or hit the endpoints.
        
        # Let's hit the report endpoint since it's the easiest to mock the data for.
        print("\n1. Testing Report Generation Job...")
        
        # Create a mock regulation
        from app.models.regulations import Regulation, RegulationVersion
        reg_id = uuid.uuid4()
        reg = Regulation(id=reg_id, jurisdiction="US", name="P12 Test Reg", source_url="mock://url")
        db.add(reg)
        
        from datetime import date, datetime, timezone
        reg_version = RegulationVersion(id=uuid.uuid4(), regulation_id=reg_id, version_label="v1", published_date=date.today(), ingested_at=datetime.now(timezone.utc))
        db.add(reg_version)
        await db.commit()
        
        # Create a mock report job
        # Note: We won't test the actual API endpoint since we don't have a valid Clerk token easily in the script, 
        # but we can enqueue a task directly to test Celery.
        
        report_id = uuid.uuid4()
        report = Report(
            id=report_id,
            org_id=org_id,
            regulation_id=reg_id,
            report_type="executive_summary",
            storage_path="",
            generated_at=datetime.now(timezone.utc)
        )
        db.add(report)
        
        job_id = uuid.uuid4()
        job = BackgroundJob(
            id=job_id,
            job_type="report",
            status=JobStatus.pending,
            payload={"report_id": str(report.id)}
        )
        db.add(job)
        await db.commit()
        
        from app.worker.tasks import task_generate_report
        print(f"Enqueuing report job {job.id} for report {report.id}...")
        task_generate_report.apply_async(
            args=[str(job.id), str(report.id)],
            queue="reports"
        )
        
        # Poll DB for job completion
        max_attempts = 30
        completed = False
        for i in range(max_attempts):
            await db.refresh(job)
            print(f"Job {job.id} status: {job.status.value}")
            if job.status == JobStatus.completed:
                completed = True
                break
            elif job.status in [JobStatus.failed, JobStatus.dead_letter]:
                print(f"Job failed with error: {job.error_message}")
                break
            await asyncio.sleep(1)
            
        if completed:
            print("[PASS] Report job completed successfully.")
            await db.refresh(report)
            print(f"Report storage_path: {report.storage_path}")
        else:
            print("[FAIL] Report job did not complete.")
            
        # 2. Testing Dead Letter Queue / Failure logic
        print("\n2. Testing Dead Letter Queue...")
        job_fail_id = uuid.uuid4()
        job_fail = BackgroundJob(
            id=job_fail_id,
            job_type="report",
            status=JobStatus.pending,
            payload={"report_id": str(uuid.uuid4())} # Invalid report ID will cause a failure
        )
        db.add(job_fail)
        await db.commit()
        
        print(f"Enqueuing failing job {job_fail.id}...")
        task_generate_report.apply_async(
            args=[str(job_fail.id), job_fail.payload["report_id"]],
            queue="reports"
        )
        
        max_attempts = 45 # More time for retries
        dead_lettered = False
        for i in range(max_attempts):
            await db.refresh(job_fail)
            if job_fail.status == JobStatus.dead_letter:
                dead_lettered = True
                print(f"Job {job_fail.id} reached dead_letter queue as expected. Error: {job_fail.error_message}")
                break
            await asyncio.sleep(1)
            
        if dead_lettered:
            print("[PASS] Failing job reached dead letter queue.")
        else:
            print(f"[FAIL] Failing job status is {job_fail.status.value}, expected dead_letter.")
            
if __name__ == "__main__":
    asyncio.run(verify_phase12())
