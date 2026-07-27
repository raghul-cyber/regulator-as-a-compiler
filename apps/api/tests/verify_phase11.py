import asyncio
import logging
import os
import sys
from uuid import uuid4

# Set up environment and path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:password@db:5432/rac_db"

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models.organizations import Organization
from app.models.regulations import Regulation, RegulationVersion
from app.models.requirements import Requirement, Severity, RequirementType, ValidationStatus, RequirementEmbedding
from app.models.policies import SystemMapping
from app.models.impacts import ImpactRecord, ImpactStatus
from app.models.reports import Notification, NotificationType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from datetime import date, datetime, timezone

async def run_tests():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # 1. Setup Test Data
        org = Organization(id=uuid4(), name="Test Org Phase 11", plan="enterprise")
        reg = Regulation(id=uuid4(), name="Phase 11 Test Regulation", jurisdiction="EU", source_url="")
        db.add_all([org, reg])
        await db.commit()
        
        now = datetime.now(timezone.utc)
        today = date.today()
        
        from app.models.documents import SourceDocument, DocumentSection, FileType
        
        # Create Version 1
        v1 = RegulationVersion(
            id=uuid4(), 
            regulation_id=reg.id, 
            version_label="1.0",
            source_document_id=None,
            diff_summary={},
            published_date=today,
            ingested_at=now
        )
        db.add(v1)
        await db.commit()
        
        doc = SourceDocument(
            id=uuid4(),
            regulation_version_id=v1.id,
            file_type=FileType.pdf,
            storage_path="",
            raw_text="Test Document",
            ocr_used=False,
            page_count=1
        )
        db.add(doc)
        await db.commit()
        
        v1.source_document_id = doc.id
        await db.commit()
        
        sec = DocumentSection(
            id=uuid4(),
            source_document_id=doc.id,
            reference_label="Section 1",
            raw_text="Test section",
            order_index=1
        )
        db.add(sec)
        await db.commit()
        
        # Create a Requirement for Version 1
        req_v1 = Requirement(
            id=uuid4(),
            regulation_version_id=v1.id,
            section_id=sec.id,
            type=RequirementType.obligation,
            title="Old Rule",
            description="Must do X.",
            severity=Severity.high,
            conditions={},
            actions={},
            evidence_required={},
            references={},
            validation_status=ValidationStatus.approved,
            confidence_score=0.9
        )
        db.add(req_v1)
        await db.commit()
        
        emb1 = RequirementEmbedding(requirement_id=req_v1.id, embedding=[1.0, 0.0, 0.0] * 512, model_used="test")
        db.add(emb1)
        await db.commit()
        
        # 1. Create a system_mapping linking an internal system to req_v1
        sys_map = SystemMapping(
            id=uuid4(),
            org_id=org.id,
            system_name="Billing System (Internal)",
            mapped_requirement_ids=[req_v1.id]
        )
        db.add(sys_map)
        await db.commit()
        
        logger.info("--- Setup Complete ---")
        
        # 2. Trigger version diff
        # Create Version 2
        v2 = RegulationVersion(
            id=uuid4(), 
            regulation_id=reg.id, 
            version_label="2.0",
            source_document_id=None,
            diff_summary={},
            published_date=today,
            ingested_at=now
        )
        db.add(v2)
        await db.commit()
        
        doc2 = SourceDocument(
            id=uuid4(),
            regulation_version_id=v2.id,
            file_type=FileType.pdf,
            storage_path="",
            raw_text="Test Document 2",
            ocr_used=False,
            page_count=1
        )
        db.add(doc2)
        await db.commit()
        
        v2.source_document_id = doc2.id
        await db.commit()
        
        sec2 = DocumentSection(
            id=uuid4(),
            source_document_id=doc2.id,
            reference_label="Section 1",
            raw_text="Test section",
            order_index=1
        )
        db.add(sec2)
        await db.commit()
        
        # Create modified Requirement for Version 2 (Cosine distance ~0 so they match, but fields differ)
        req_v2 = Requirement(
            id=uuid4(),
            regulation_version_id=v2.id,
            section_id=sec2.id,
            type=RequirementType.obligation,
            title="Modified Rule",
            description="Must do X and Y.",
            severity=Severity.critical, # Severity changed from high to critical
            conditions={},
            actions={},
            evidence_required={},
            references={},
            validation_status=ValidationStatus.approved,
            confidence_score=0.9
        )
        db.add(req_v2)
        await db.commit()
        
        emb2 = RequirementEmbedding(requirement_id=req_v2.id, embedding=[1.0, 0.0, 0.0] * 512, model_used="test")
        db.add(emb2)
        await db.commit()
        
        # Run diff engine
        from app.pipelines.diff_engine import compute_version_diff
        await compute_version_diff(v1.id, v2.id, db)
        
        # 3. Confirm impact record is generated referencing system_mapping
        impact_stmt = select(ImpactRecord).where(ImpactRecord.system_mapping_id == sys_map.id)
        impacts = (await db.execute(impact_stmt)).scalars().all()
        
        assert len(impacts) == 1, f"Expected 1 ImpactRecord, got {len(impacts)}"
        impact = impacts[0]
        
        # Confirm impact severity inherits from the requirement (new requirement severity is critical)
        assert impact.severity == Severity.critical, f"Expected severity critical, got {impact.severity}"
        print("[PASS] 1 & 2. System Mapping correctly spawned Impact Record upon Requirement modification, inheriting severity.")
        
        # Test override
        impact.overridden_severity = Severity.low
        await db.commit()
        await db.refresh(impact)
        
        # Requirement severity should still be critical
        await db.refresh(req_v2)
        assert req_v2.severity == Severity.critical
        assert impact.overridden_severity == Severity.low
        print("[PASS] 3. Org-level override changes the displayed severity without mutating the underlying requirement's severity.")
        
        # 4. Confirm notification row is created
        notif_stmt = select(Notification).where(Notification.org_id == org.id)
        notifs = (await db.execute(notif_stmt)).scalars().all()
        
        assert len(notifs) == 1, f"Expected 1 Notification, got {len(notifs)}"
        notif = notifs[0]
        assert notif.type == NotificationType.impact_alert
        assert notif.payload["system_name"] == "Billing System (Internal)"
        assert notif.payload["severity"] == "critical"
        
        # Verify Dashboard API
        from httpx import AsyncClient
        from app.main import app
        from app.core.auth import get_current_user
        from app.models.users import User, UserRole
        
        # Override dependency
        mock_admin = User(id=uuid4(), clerk_user_id="admin_123", email="admin@test.com", org_id=org.id, role=UserRole.admin)
        mock_viewer = User(id=uuid4(), clerk_user_id="view_123", email="view@test.com", org_id=org.id, role=UserRole.developer)
        mock_other_org = User(id=uuid4(), clerk_user_id="other_123", email="other@test.com", org_id=uuid4(), role=UserRole.admin)
        
        # We need to simulate the dependency
        app.dependency_overrides[get_current_user] = lambda: mock_admin
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/dashboard/summary")
            assert response.status_code == 200
            data = response.json()
            assert "affected_systems" in data
            affected_systems = data["affected_systems"]
            assert len(affected_systems) >= 1
            # Check override
            override_found = False
            for sys in affected_systems:
                if sys["impact_record_id"] == str(impact.id):
                    assert sys["severity"] == "low"
                    override_found = True
            assert override_found, "Affected system override not found in dashboard"
        
        print("[PASS] 4. 'affected systems' dashboard view updates and a notification row is created.")
        
        # 5. Confirm system_mappings CRUD is properly org-scoped and role-gated.
        # Test Admin creates system
        app.dependency_overrides[get_current_user] = lambda: mock_admin
        async with AsyncClient(app=app, base_url="http://test") as ac:
            res = await ac.post("/api/v1/systems", json={"system_name": "API Gateway", "mapped_requirement_ids": [str(req_v1.id)]})
            assert res.status_code == 200
            created_sys_id = res.json()["id"]
        
        # Test non-admin cannot create system
        app.dependency_overrides[get_current_user] = lambda: mock_viewer
        async with AsyncClient(app=app, base_url="http://test") as ac:
            res = await ac.post("/api/v1/systems", json={"system_name": "Should Fail", "mapped_requirement_ids": []})
            assert res.status_code == 403
            
        # Test other org cannot see system
        app.dependency_overrides[get_current_user] = lambda: mock_other_org
        async with AsyncClient(app=app, base_url="http://test") as ac:
            res = await ac.get("/api/v1/systems")
            assert res.status_code == 200
            assert len(res.json()) == 0
            
        print("[PASS] 5. system_mappings CRUD is properly org-scoped and role-gated.")
        print("\nPhase 11 successfully verified end-to-end!\n")

if __name__ == "__main__":
    asyncio.run(run_tests())
