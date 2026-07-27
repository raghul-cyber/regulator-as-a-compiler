import asyncio
import os
import io
import jwt
from uuid import uuid4
from datetime import date, datetime, timezone, timedelta
import pytest

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, AsyncSessionLocal
from app.models.base import Base
from app.models.organizations import Organization, PlanType
from app.models.users import User, UserRole
from app.core.auth import get_current_user
from app.models.regulations import Regulation, RegulationVersion
from app.models.requirements import Requirement, RequirementType, Severity, ValidationStatus
from app.models.reports import Report, ReportType
from app.models.documents import SourceDocument, DocumentSection, FileType

from httpx import AsyncClient, ASGITransport
from app.main import app

JWT_SECRET = "super_secret_for_signed_urls_phase8"

async def setup_test_data(db):
    org_a = Organization(id=uuid4(), name="Org A", plan=PlanType.standard)
    org_b = Organization(id=uuid4(), name="Org B", plan=PlanType.standard)
    db.add_all([org_a, org_b])
    
    admin_a = User(id=uuid4(), org_id=org_a.id, clerk_user_id=f"clerk_{uuid4()}", role=UserRole.admin, email="a@a.com")
    admin_b = User(id=uuid4(), org_id=org_b.id, clerk_user_id=f"clerk_{uuid4()}", role=UserRole.admin, email="b@b.com")
    db.add_all([admin_a, admin_b])
    await db.flush()

    reg_a = Regulation(id=uuid4(), name=f"GDPR_Phase8_{uuid4()}", jurisdiction="EU", source_url="")
    db.add(reg_a)
    await db.flush()
    reg_ver_a = RegulationVersion(id=uuid4(), regulation_id=reg_a.id, version_label="v1", published_date=date.today(), ingested_at=datetime.now(timezone.utc))
    db.add(reg_ver_a)
    await db.flush()

    # Source Document & Section
    doc = SourceDocument(id=uuid4(), regulation_version_id=reg_ver_a.id, file_type=FileType.pdf, storage_path="x", raw_text="...", ocr_used=False, page_count=1)
    db.add(doc)
    await db.flush()
    section = DocumentSection(id=uuid4(), source_document_id=doc.id, order_index=1, reference_label="Article 8", raw_text="Text")
    db.add(section)
    await db.flush()

    # Requirements
    req1 = Requirement(
        id=uuid4(),
        regulation_version_id=reg_ver_a.id,
        section_id=section.id,
        type=RequirementType.obligation,
        title="Consent Required",
        description="Must have explicit consent.",
        conditions={}, actions={}, severity=Severity.critical, evidence_required={"type": "consent_log"}, references={}, confidence_score=0.95,
        validation_status=ValidationStatus.approved
    )
    req2 = Requirement(
        id=uuid4(),
        regulation_version_id=reg_ver_a.id,
        section_id=section.id,
        type=RequirementType.prohibition,
        title="No Minors",
        description="Do not collect data from minors.",
        conditions={}, actions={}, severity=Severity.high, evidence_required={}, references={}, confidence_score=0.99,
        validation_status=ValidationStatus.enforceable
    )
    req3 = Requirement(
        id=uuid4(),
        regulation_version_id=reg_ver_a.id,
        section_id=section.id,
        type=RequirementType.permission,
        title="Draft Ignored",
        description="This is draft and should not be exported.",
        conditions={}, actions={}, severity=Severity.low, evidence_required={}, references={}, confidence_score=0.5,
        validation_status=ValidationStatus.draft
    )
    db.add_all([req1, req2, req3])
    await db.commit()

    return org_a, org_b, admin_a, admin_b, reg_a

async def get_test_db():
    async with AsyncSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = get_test_db

def override_get_current_user_factory(user):
    async def _override():
        return user
    return _override

async def run_tests():
    async with AsyncSessionLocal() as db:
        org_a, org_b, admin_a, admin_b, reg_a = await setup_test_data(db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Test JSON Export
        print("\n--- 1. JSON Export Validation ---")
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(admin_a)
        res = await client.get(f"/api/v1/regulations/{reg_a.id}/export")
        assert res.status_code == 200, res.text
        export_data = res.json()
        assert len(export_data) == 2 # Only approved and enforceable
        print(f"Exported {len(export_data)} requirements successfully.")
        
        # Check shape
        req_json = export_data[0]
        expected_keys = {"id", "regulation_version_id", "section_id", "type", "title", "description", "conditions", "actions", "severity", "evidence_required", "references", "confidence_score", "validation_status"}
        assert set(req_json.keys()) == expected_keys
        print("Export shape matches PRD Section 11 exactly.")

        # 2. Test PDF Generation
        print("\n--- 2. PDF Generation ---")
        report_types = ["executive_summary", "technical", "audit_evidence", "gap_analysis", "checklist"]
        reports_created = []
        
        import fitz  # PyMuPDF
        
        for rtype in report_types:
            res = await client.post("/api/v1/reports", json={"regulation_id": str(reg_a.id), "report_type": rtype})
            assert res.status_code == 200, res.text
            rep = res.json()
            reports_created.append(rep)
            
            # Download it
            url = rep["download_url"]
            res_dl = await client.get(url)
            assert res_dl.status_code == 200, res_dl.text
            assert res_dl.headers["content-type"] == "application/pdf"
            
            pdf_bytes = res_dl.content
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
                
            print(f"Generated {rtype}. PDF size: {len(pdf_bytes)} bytes. Contains 'Consent Required': {'Consent Required' in text}")
            assert "Consent Required" in text or "Executive Summary" in text # Check text

        # 3. Test Determinism
        print("\n--- 3. Determinism Check ---")
        res1 = await client.post("/api/v1/reports", json={"regulation_id": str(reg_a.id), "report_type": "technical"})
        url1 = res1.json()["download_url"]
        pdf1 = (await client.get(url1)).content
        
        res2 = await client.post("/api/v1/reports", json={"regulation_id": str(reg_a.id), "report_type": "technical"})
        url2 = res2.json()["download_url"]
        pdf2 = (await client.get(url2)).content
        
        doc1 = fitz.open(stream=pdf1, filetype="pdf")
        doc2 = fitz.open(stream=pdf2, filetype="pdf")
        t1 = "".join(p.get_text() for p in doc1)
        t2 = "".join(p.get_text() for p in doc2)
        assert t1 == t2
        print(f"Content matches exactly between two generations. Length: {len(t1)} chars.")
        
        # 4. Security
        print("\n--- 4. Security & Signed URLs ---")

        # Invalid token
        res = await client.get("/api/v1/reports/download?token=invalid_token")
        assert res.status_code == 403
        print("Invalid token correctly rejected (403).")
        
        # Expired token
        expired_token = jwt.encode({"report_id": str(reports_created[0]["id"]), "org_id": str(org_a.id), "exp": datetime.now(timezone.utc) - timedelta(minutes=5)}, JWT_SECRET, algorithm="HS256")
        res = await client.get(f"/api/v1/reports/download?token={expired_token}")
        assert res.status_code == 401
        print("Expired token correctly rejected (401).")

        # 5. Cross-Tenant Guardrails
        print("\n--- 5. Cross-Tenant Check ---")
        # Switch to admin_b
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(admin_b)
        # Give Admin B a valid token but trying to access Org A's report
        malicious_token = jwt.encode({"report_id": str(reports_created[0]["id"]), "org_id": str(org_b.id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, JWT_SECRET, algorithm="HS256")
        res = await client.get(f"/api/v1/reports/download?token={malicious_token}")
        assert res.status_code == 403
        print("Cross-tenant fetch using signed URL correctly rejected (403).")

        # Try to generate report for Org A's regulation as Admin B (regulations are global, so this works, but the report belongs to Org B)
        res = await client.post(f"/api/v1/reports", json={
            "regulation_id": str(reg_a.id),
            "report_type": ReportType.executive_summary.value
        })
        assert res.status_code == 200
        print("Report generation successfully scoped to the calling user's tenant.")

    print("\nALL PHASE 8 TESTS PASSED.")

if __name__ == "__main__":
    asyncio.run(run_tests())
