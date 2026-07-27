import asyncio
from uuid import uuid4
import httpx
from httpx import ASGITransport
from datetime import datetime, date
from app.main import app as main_app
from app.models.users import User, UserRole
from app.core.auth import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from sqlalchemy import select, text
from app.models.regulations import Regulation, RegulationVersion
from app.models.documents import SourceDocument, DocumentSection, FileType
from app.models.requirements import Requirement, RequirementType, Severity, ValidationStatus
from app.models.organizations import Organization
from app.models.audit import AuditLog

async def setup_test_data(db: AsyncSession):
    # Ensure Org exists
    org = (await db.execute(select(Organization))).scalars().first()
    if not org:
        org = Organization(id=uuid4(), name="Test Org")
        db.add(org)
        await db.flush()
        
    # Setup users with unique clerk_user_ids to avoid unique constraints
    admin_user = User(id=uuid4(), org_id=org.id, clerk_user_id=f"clerk_admin_{uuid4()}", role=UserRole.admin, email="admin@orga.com")
    comp_officer = User(id=uuid4(), org_id=org.id, clerk_user_id=f"clerk_co_{uuid4()}", role=UserRole.compliance_officer, email="co@orga.com")
    dev_user = User(id=uuid4(), org_id=org.id, clerk_user_id=f"clerk_dev_{uuid4()}", role=UserRole.developer, email="dev@orga.com")
    db.add_all([admin_user, comp_officer, dev_user])
    await db.flush()

    # Setup regulation + version + doc + section
    reg = Regulation(id=uuid4(), name="GDPR Phase6", jurisdiction="EU", source_url="")
    db.add(reg)
    await db.flush()
    reg_ver = RegulationVersion(id=uuid4(), regulation_id=reg.id, version_label="Draft", published_date=date.today(), ingested_at=datetime.now())
    db.add(reg_ver)
    await db.flush()
    
    # Needs current_version_id
    reg.current_version_id = reg_ver.id
    
    doc = SourceDocument(id=uuid4(), regulation_version_id=reg_ver.id, file_type=FileType.pdf, storage_path="x", raw_text="Full doc text...", ocr_used=False, page_count=1)
    db.add(doc)
    await db.flush()
    section = DocumentSection(id=uuid4(), source_document_id=doc.id, order_index=1, reference_label="Article 5", raw_text="Consent is important...")
    db.add(section)
    await db.flush()
    
    # Create Requirements
    req1 = Requirement(
        id=uuid4(), regulation_version_id=reg_ver.id, section_id=section.id,
        type=RequirementType.obligation, title="Req 1", description="Must have consent",
        conditions={}, actions={}, severity=Severity.low, evidence_required={}, references={},
        confidence_score=0.9, validation_status=ValidationStatus.pending_review
    )
    req2 = Requirement(
        id=uuid4(), regulation_version_id=reg_ver.id, section_id=section.id,
        type=RequirementType.prohibition, title="Req 2", description="Do not share data",
        conditions={}, actions={}, severity=Severity.high, evidence_required={}, references={},
        confidence_score=0.9, validation_status=ValidationStatus.draft
    )
    db.add_all([req1, req2])
    await db.commit()
    
    return org, admin_user, comp_officer, dev_user, reg, reg_ver, req1, req2, section

async def run_tests():
    print("--- Phase 6 Verification ---")
    transport = ASGITransport(app=main_app)
    
    async with AsyncSessionLocal() as db:
        org, admin, co, dev, reg, reg_ver, req1, req2, section = await setup_test_data(db)
        
    main_app.dependency_overrides[get_current_user] = lambda: co

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        print("\n1. Filter Requirements by type/severity/status...")
        res = await client.get(f"/api/regulations/{reg.id}/requirements?severity=low&status=pending_review")
        print("Filter API Response:", res.status_code, "Items:", len(res.json()["items"]))
        
        async with AsyncSessionLocal() as db:
            db_count = (await db.execute(select(Requirement).where(Requirement.severity == Severity.low, Requirement.validation_status == ValidationStatus.pending_review))).scalars().all()
            print("DB Direct Query Count:", len(db_count))
            
        print("\n2. Keyword Search...")
        res_search = await client.get(f"/api/regulations/{reg.id}/requirements?search=consent")
        print("Search API Response Items:", len(res_search.json()["items"]))
        if len(res_search.json()["items"]) > 0:
            print("Found requirement title:", res_search.json()["items"][0]["title"])
            
        print("\n3. Reference Traceability...")
        # Since references is JSON, we can check section_id which maps to the document section
        print("Section ID linked to requirement:", res_search.json()["items"][0]["section_id"])
        
        print("\n4. Approve pending_review requirement...")
        payload = {"validation_status": "approved"}
        res_approve = await client.patch(f"/api/requirements/{req1.id}", json=payload)
        print("Approve Response:", res_approve.status_code)
        if res_approve.status_code == 200:
            print("Validation Status Updated:", res_approve.json()["validation_status"])
            print("Reviewed By:", res_approve.json()["reviewed_by_user_id"])
        
        async with AsyncSessionLocal() as db:
            audit = (await db.execute(select(AuditLog).where(AuditLog.entity_id == req1.id))).scalars().first()
            if audit:
                print("Audit Log generated:", audit.action)
                
        print("\n5. Reject requirement without reason...")
        payload_reject_no_reason = {"validation_status": "draft"}
        res_reject_no_reason = await client.patch(f"/api/requirements/{req1.id}", json=payload_reject_no_reason)
        print("Reject without reason Response:", res_reject_no_reason.status_code, res_reject_no_reason.json())

        print("\nReject requirement WITH reason...")
        payload_reject = {"validation_status": "draft", "rejection_reason": "Needs more clarity"}
        res_reject = await client.patch(f"/api/requirements/{req1.id}", json=payload_reject)
        print("Reject with reason Response:", res_reject.status_code)
        if res_reject.status_code == 200:
            print("Rejection Reason stored:", res_reject.json()["rejection_reason"])
            
        print("\n6. As Developer, Approve/Reject...")
        main_app.dependency_overrides[get_current_user] = lambda: dev
        res_dev_approve = await client.patch(f"/api/requirements/{req1.id}", json={"validation_status": "approved"})
        print("Developer Approve Response:", res_dev_approve.status_code, res_dev_approve.json())

if __name__ == "__main__":
    asyncio.run(run_tests())
