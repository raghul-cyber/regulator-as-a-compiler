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
from sqlalchemy import select, func, text
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
        
    # Setup users with unique clerk_user_ids
    admin_user = User(id=uuid4(), org_id=org.id, clerk_user_id=f"clerk_admin_{uuid4()}", role=UserRole.admin, email="admin@orga.com")
    auditor_user = User(id=uuid4(), org_id=org.id, clerk_user_id=f"clerk_auditor_{uuid4()}", role=UserRole.auditor, email="auditor@orga.com")
    db.add_all([admin_user, auditor_user])
    await db.flush()

    # Setup regulation
    reg = Regulation(id=uuid4(), name=f"Phase7_Reg_{uuid4()}", jurisdiction="EU", source_url="")
    db.add(reg)
    await db.flush()
    reg_ver = RegulationVersion(id=uuid4(), regulation_id=reg.id, version_label="Draft", published_date=date.today(), ingested_at=datetime.now())
    db.add(reg_ver)
    await db.flush()
    
    # Document and Section
    doc = SourceDocument(id=uuid4(), regulation_version_id=reg_ver.id, file_type=FileType.pdf, storage_path="x", raw_text="...", ocr_used=False, page_count=1)
    db.add(doc)
    await db.flush()
    section = DocumentSection(id=uuid4(), source_document_id=doc.id, order_index=1, reference_label="Article 7", raw_text="Text")
    db.add(section)
    await db.flush()
    
    # Requirements
    req1 = Requirement(id=uuid4(), regulation_version_id=reg_ver.id, section_id=section.id, type=RequirementType.obligation, title="Req 1", description="Must have consent", conditions={}, actions={}, severity=Severity.critical, evidence_required={}, references={}, confidence_score=0.9, validation_status=ValidationStatus.pending_review)
    req2 = Requirement(id=uuid4(), regulation_version_id=reg_ver.id, section_id=section.id, type=RequirementType.prohibition, title="Req 2", description="Do not share data", conditions={}, actions={}, severity=Severity.high, evidence_required={}, references={}, confidence_score=0.9, validation_status=ValidationStatus.draft)
    req3 = Requirement(id=uuid4(), regulation_version_id=reg_ver.id, section_id=section.id, type=RequirementType.permission, title="Req 3", description="May delete", conditions={}, actions={}, severity=Severity.low, evidence_required={}, references={}, confidence_score=0.9, validation_status=ValidationStatus.approved)
    req4 = Requirement(id=uuid4(), regulation_version_id=reg_ver.id, section_id=section.id, type=RequirementType.obligation, title="Req 4", description="Extra", conditions={}, actions={}, severity=Severity.critical, evidence_required={}, references={}, confidence_score=0.9, validation_status=ValidationStatus.enforceable)
    db.add_all([req1, req2, req3, req4])
    await db.flush()
    
    # Audit Logs
    audit1 = AuditLog(id=uuid4(), org_id=org.id, actor_id=admin_user.id, action="requirement.created", entity_type="requirement", entity_id=req1.id, metadata_payload={}, created_at=datetime(2026, 7, 1))
    audit2 = AuditLog(id=uuid4(), org_id=org.id, actor_id=admin_user.id, action="requirement.status_changed", entity_type="requirement", entity_id=req2.id, metadata_payload={}, created_at=datetime(2026, 7, 2))
    audit3 = AuditLog(id=uuid4(), org_id=org.id, actor_id=admin_user.id, action="requirement.status_changed", entity_type="requirement", entity_id=req3.id, metadata_payload={}, created_at=datetime(2026, 7, 3))
    db.add_all([audit1, audit2, audit3])
    
    await db.commit()
    return org, admin_user, auditor_user, req1, req2, req3, req4

async def run_tests():
    print("--- Phase 7 Verification ---")
    transport = ASGITransport(app=main_app)
    
    async with AsyncSessionLocal() as db:
        org, admin, auditor, req1, req2, req3, req4 = await setup_test_data(db)
        
        print("\n1. Stat Card DB query verification")
        # Direct DB queries
        db_total = (await db.execute(select(func.count(Requirement.id)))).scalar()
        db_obligations = (await db.execute(select(func.count(Requirement.id)).where(Requirement.type == RequirementType.obligation))).scalar()
        db_critical = (await db.execute(select(func.count(Requirement.id)).where(Requirement.severity == Severity.critical))).scalar()
        
    main_app.dependency_overrides[get_current_user] = lambda: admin

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/dashboard/summary")
        data = res.json()
        
        print(f"Total Requirements -> API: {data['total_requirements']}, DB: {db_total} (Match: {data['total_requirements'] == db_total})")
        print(f"Obligations -> API: {data['counts_by_type'].get('obligation', 0)}, DB: {db_obligations} (Match: {data['counts_by_type'].get('obligation', 0) == db_obligations})")
        print(f"Critical -> API: {data['counts_by_severity'].get('critical', 0)}, DB: {db_critical} (Match: {data['counts_by_severity'].get('critical', 0) == db_critical})")

        print("\n2. High-Risk Controls Isolation")
        high_risk_ids = [r['id'] for r in data['high_risk_controls']]
        print(f"Expected in High Risk: req1 ({str(req1.id)}), req2 ({str(req2.id)})")
        print(f"Actually in High Risk: {high_risk_ids}")
        assert str(req1.id) in high_risk_ids
        assert str(req2.id) in high_risk_ids
        assert str(req3.id) not in high_risk_ids # low/approved
        assert str(req4.id) not in high_risk_ids # critical but enforceable
        print("High Risk Filter PASS.")
        
        # Approve req1
        print("Approving req1...")
        await client.patch(f"/api/requirements/{req1.id}", json={"validation_status": "approved"})
        
        # Re-fetch dashboard
        res2 = await client.get("/api/v1/dashboard/summary")
        data2 = res2.json()
        high_risk_ids2 = [r['id'] for r in data2['high_risk_controls']]
        print(f"After approval, is req1 in high risk? {str(req1.id) in high_risk_ids2}")
        
        print("\n3. Recent Activity Order")
        recent = data2['recent_activity']
        # The latest one should be the audit log for req1's approval (just generated)
        print(f"Latest activity: {recent[0]['action']} on {recent[0]['title']}")
        print(f"Is latest activity 'requirement.status_changed'? {recent[0]['action'] == 'requirement.status_changed'}")
        # Dates should be descending
        dates = [r['created_at'] for r in recent]
        is_descending = all(dates[i] >= dates[i+1] for i in range(len(dates)-1))
        print(f"Are activities ordered descending? {is_descending}")
        
        print("\n4. Auditor Read-Only Access")
        main_app.dependency_overrides[get_current_user] = lambda: auditor
        res_auditor = await client.get("/api/v1/dashboard/summary")
        print(f"Auditor can fetch dashboard? Status {res_auditor.status_code}")
        
        # Try to approve as auditor
        res_auditor_patch = await client.patch(f"/api/requirements/{req2.id}", json={"validation_status": "approved"})
        print(f"Auditor can approve? Status {res_auditor_patch.status_code} (Expect 403)")

if __name__ == "__main__":
    asyncio.run(run_tests())
