import asyncio
import os
import io
from uuid import uuid4
from datetime import date, datetime, timezone
import pytest

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db, AsyncSessionLocal
from app.models.organizations import Organization, PlanType
from app.models.users import User, UserRole
from app.core.auth import get_current_user
from app.models.regulations import Regulation, RegulationVersion
from app.models.requirements import Requirement, RequirementEmbedding, RequirementType, Severity, ValidationStatus
from app.models.documents import SourceDocument, DocumentSection, FileType
from app.models.diffs import RequirementDiff, DiffStatus

from httpx import AsyncClient, ASGITransport
from app.main import app

async def setup_test_data(db: AsyncSession):
    # Setup users/org
    org_a = Organization(id=uuid4(), name="Org A", plan=PlanType.standard)
    db.add(org_a)
    admin_a = User(id=uuid4(), org_id=org_a.id, clerk_user_id=f"clerk_{uuid4()}", role=UserRole.admin, email="a@a.com")
    db.add(admin_a)
    await db.flush()

    # Regulation
    reg_a = Regulation(id=uuid4(), name=f"GDPR_Phase10_{uuid4()}", jurisdiction="EU", source_url="")
    db.add(reg_a)
    await db.flush()

    # Old version (v1)
    v1_id = uuid4()
    reg_ver_1 = RegulationVersion(id=v1_id, regulation_id=reg_a.id, version_label="v1", published_date=date.today(), ingested_at=datetime.now(timezone.utc))
    db.add(reg_ver_1)
    await db.flush()
    reg_a.current_version_id = v1_id
    await db.flush()

    # Create Source Doc and Section
    doc = SourceDocument(id=uuid4(), regulation_version_id=v1_id, file_type=FileType.pdf, storage_path="x", raw_text="...", ocr_used=False, page_count=1)
    db.add(doc)
    await db.flush()
    section = DocumentSection(id=uuid4(), source_document_id=doc.id, order_index=1, reference_label="Article 8", raw_text="Text")
    db.add(section)
    await db.flush()

    # Add Requirements for v1
    req_v1_1 = Requirement(
        id=uuid4(), regulation_version_id=v1_id, section_id=section.id, type=RequirementType.obligation,
        title="Base Req 1", description="This is an unchanged requirement.", conditions={}, actions={},
        severity=Severity.medium, evidence_required={}, references={}, confidence_score=0.9, validation_status=ValidationStatus.approved
    )
    req_v1_2 = Requirement(
        id=uuid4(), regulation_version_id=v1_id, section_id=section.id, type=RequirementType.prohibition,
        title="Base Req 2", description="This requirement will be modified.", conditions={}, actions={},
        severity=Severity.high, evidence_required={}, references={}, confidence_score=0.9, validation_status=ValidationStatus.approved
    )
    req_v1_3 = Requirement(
        id=uuid4(), regulation_version_id=v1_id, section_id=section.id, type=RequirementType.permission,
        title="Base Req 3", description="This requirement will be removed.", conditions={}, actions={},
        severity=Severity.low, evidence_required={}, references={}, confidence_score=0.9, validation_status=ValidationStatus.approved
    )
    db.add_all([req_v1_1, req_v1_2, req_v1_3])
    await db.flush()

    emb1 = RequirementEmbedding(requirement_id=req_v1_1.id, embedding=[1.0, 0.0, 0.0] * 512, model_used="test")
    emb2 = RequirementEmbedding(requirement_id=req_v1_2.id, embedding=[0.0, 1.0, 0.0] * 512, model_used="test")
    emb3 = RequirementEmbedding(requirement_id=req_v1_3.id, embedding=[0.0, 0.0, 1.0] * 512, model_used="test")
    db.add_all([emb1, emb2, emb3])
    await db.flush()

    # New version (v2)
    v2_id = uuid4()
    reg_ver_2 = RegulationVersion(id=v2_id, regulation_id=reg_a.id, version_label="v2", published_date=date.today(), ingested_at=datetime.now(timezone.utc))
    db.add(reg_ver_2)
    await db.flush()

    # Create Source Doc and Section for v2
    doc2 = SourceDocument(id=uuid4(), regulation_version_id=v2_id, file_type=FileType.pdf, storage_path="x", raw_text="...", ocr_used=False, page_count=1)
    db.add(doc2)
    await db.flush()
    section2 = DocumentSection(id=uuid4(), source_document_id=doc2.id, order_index=1, reference_label="Article 8", raw_text="Text")
    db.add(section2)
    await db.flush()

    # Add Requirements for v2
    # req 1 remains (close embedding, same fields)
    req_v2_1 = Requirement(
        id=uuid4(), regulation_version_id=v2_id, section_id=section2.id, type=RequirementType.obligation,
        title="Base Req 1", description="This is an unchanged requirement.", conditions={}, actions={},
        severity=Severity.medium, evidence_required={}, references={}, confidence_score=0.9, validation_status=ValidationStatus.approved
    )
    # req 2 modified (close embedding, diff severity)
    req_v2_2 = Requirement(
        id=uuid4(), regulation_version_id=v2_id, section_id=section2.id, type=RequirementType.prohibition,
        title="Base Req 2", description="This requirement will be modified.", conditions={}, actions={},
        severity=Severity.critical, evidence_required={}, references={}, confidence_score=0.9, validation_status=ValidationStatus.approved
    )
    # req 3 is missing (removed)
    # req 4 is newly added
    req_v2_4 = Requirement(
        id=uuid4(), regulation_version_id=v2_id, section_id=section2.id, type=RequirementType.obligation,
        title="New Req", description="This is a newly added requirement.", conditions={}, actions={},
        severity=Severity.medium, evidence_required={}, references={}, confidence_score=0.9, validation_status=ValidationStatus.approved
    )
    db.add_all([req_v2_1, req_v2_2, req_v2_4])
    await db.flush()

    # Orthogonal vectors so cosine similarity is 0 (distance 1)
    emb2_1 = RequirementEmbedding(requirement_id=req_v2_1.id, embedding=[1.0, 0.0, 0.0] * 512, model_used="test")
    emb2_2 = RequirementEmbedding(requirement_id=req_v2_2.id, embedding=[0.0, 1.0, 0.0] * 512, model_used="test")
    emb2_4 = RequirementEmbedding(requirement_id=req_v2_4.id, embedding=[0.5, 0.5, 0.5] * 512, model_used="test")
    db.add_all([emb2_1, emb2_2, emb2_4])
    await db.commit()

    return admin_a, reg_a, reg_ver_1, reg_ver_2, [req_v1_1, req_v1_2, req_v1_3], [req_v2_1, req_v2_2, req_v2_4]

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
        admin_a, reg_a, v1, v2, v1_reqs, v2_reqs = await setup_test_data(db)
        
        # Test 1 & 2: Trigger the diff engine directly and verify outputs
        print("\n--- Testing Diff Engine Pipeline ---")
        from app.pipelines.diff_engine import compute_version_diff
        summary = await compute_version_diff(v1.id, v2.id, db)
        
        print(f"Diff Summary: {summary}")
        assert summary["added"] == 1
        assert summary["removed"] == 1
        assert summary["modified"] == 1
        assert summary["unchanged"] == 1
        print("[PASS] compute_version_diff correctly identified added/removed/modified/unchanged requirements.")

        # Re-fetch v2 to check if diff_summary is populated
        stmt = select(RegulationVersion).where(RegulationVersion.id == v2.id)
        v2_reloaded = (await db.execute(stmt)).scalar_one()
        assert v2_reloaded.diff_summary == summary
        print("[PASS] diff_summary automatically populated on RegulationVersion.")
        
        # Update current version to v2 for API tests
        reg_a.current_version_id = v2.id
        await db.commit()

    # Test 3: API Test
    print("\n--- Testing API Endpoints ---")
    app.dependency_overrides[get_current_user] = override_get_current_user_factory(admin_a)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/regulations/{reg_a.id}/diff")
        assert res.status_code == 200, res.text
        data = res.json()
        
        assert len(data["added"]) == 1
        assert data["added"][0]["title"] == "New Req"
        print("[PASS] GET /api/regulations/{id}/diff returns 'added' correctly.")
        
        assert len(data["removed"]) == 1
        assert data["removed"][0]["title"] == "Base Req 3"
        print("[PASS] GET /api/regulations/{id}/diff returns 'removed' correctly.")
        
        assert len(data["modified"]) == 1
        mod = data["modified"][0]
        assert mod["old"]["severity"] == "high"
        assert mod["new"]["severity"] == "critical"
        print("[PASS] GET /api/regulations/{id}/diff returns 'modified' capturing field-level changes correctly.")
        
        print("\nPhase 10 successfully verified end-to-end!")

if __name__ == "__main__":
    asyncio.run(run_tests())
