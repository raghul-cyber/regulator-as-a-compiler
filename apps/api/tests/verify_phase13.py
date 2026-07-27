import asyncio
import logging
import os
import sys
from uuid import uuid4
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:password@db:5432/rac_db"

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models.organizations import Organization
from app.models.regulations import Regulation, RegulationVersion
from app.models.requirements import Requirement, Severity, RequirementType, ValidationStatus, RequirementEmbedding
from app.models.documents import SourceDocument, DocumentSection, FileType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_tests():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        logger.info("=== Phase 13 Verification Setup ===")
        org = Organization(id=uuid4(), name="Test Org Phase 13 Search", plan="enterprise")
        reg = Regulation(id=uuid4(), name="Phase 13 GDPR Search Test", jurisdiction="EU", source_url="")
        db.add_all([org, reg])
        await db.commit()
        
        v1 = RegulationVersion(
            id=uuid4(), 
            regulation_id=reg.id, 
            version_label="v1.0",
            published_date=date.today(),
            ingested_at=datetime.now(timezone.utc)
        )
        db.add(v1)
        await db.commit()
        reg.current_version_id = v1.id
        await db.commit()
        
        doc = SourceDocument(
            id=uuid4(), regulation_version_id=v1.id, file_type=FileType.pdf,
            storage_path="test_p13.pdf", raw_text="GDPR Search Document", ocr_used=False, page_count=5
        )
        db.add(doc)
        await db.commit()
        
        sec1 = DocumentSection(id=uuid4(), source_document_id=doc.id, order_index=1, reference_label="Art. 6", raw_text="Processing of personal data requires explicit user consent.")
        sec2 = DocumentSection(id=uuid4(), source_document_id=doc.id, order_index=2, reference_label="Art. 7", raw_text="Conditions for consent in marketing communications.")
        sec3 = DocumentSection(id=uuid4(), source_document_id=doc.id, order_index=3, reference_label="Art. 89", raw_text="Archiving purposes in the public interest, scientific or historical research.")
        db.add_all([sec1, sec2, sec3])
        await db.commit()
        
        req_consent_1 = Requirement(
            id=uuid4(), regulation_version_id=v1.id, section_id=sec1.id,
            type=RequirementType.obligation, title="GDPR Data Processing Consent",
            description="Organizations must obtain clear and unambiguous consent before processing user personal data.",
            conditions={}, actions={}, severity=Severity.critical, evidence_required={}, references={},
            confidence_score=0.95, validation_status=ValidationStatus.approved
        )
        req_consent_2 = Requirement(
            id=uuid4(), regulation_version_id=v1.id, section_id=sec2.id,
            type=RequirementType.obligation, title="Marketing Communication Opt-In",
            description="Direct marketing requires prior opt-in consent from the data subject.",
            conditions={}, actions={}, severity=Severity.high, evidence_required={}, references={},
            confidence_score=0.90, validation_status=ValidationStatus.approved
        )
        req_research = Requirement(
            id=uuid4(), regulation_version_id=v1.id, section_id=sec3.id,
            type=RequirementType.permission, title="Scientific Research Exemption",
            description="Further processing for scientific research purposes is not considered incompatible with initial purposes.",
            conditions={}, actions={}, severity=Severity.low, evidence_required={}, references={},
            confidence_score=0.85, validation_status=ValidationStatus.approved
        )
        db.add_all([req_consent_1, req_consent_2, req_research])
        await db.commit()
        
        # Attach unit-length test vector embeddings (1536 dim)
        # We make req_consent_1 and req_consent_2 very similar (cosine distance close to 0)
        vec_consent_1 = [0.1234, 0.9876] + [0.0] * 1534
        vec_consent_2 = [0.1230, 0.9870] + [0.0] * 1534
        vec_research = [0.9876, -0.1234] + [0.0] * 1534
        
        emb1 = RequirementEmbedding(requirement_id=req_consent_1.id, embedding=vec_consent_1, model_used="test-3-small")
        emb2 = RequirementEmbedding(requirement_id=req_consent_2.id, embedding=vec_consent_2, model_used="test-3-small")
        emb3 = RequirementEmbedding(requirement_id=req_research.id, embedding=vec_research, model_used="test-3-small")
        db.add_all([emb1, emb2, emb3])
        await db.commit()
        
        logger.info("Test requirements and embeddings created successfully.")
        
        # Test 1: Keyword search via router function get_regulation_requirements
        logger.info("\n--- TEST 1: Keyword Search Relevance Ranking ---")
        from app.api.routers.regulations import get_regulation_requirements
        from app.models.users import User, UserRole
        mock_user = User(id=uuid4(), email="admin@test.com", role=UserRole.admin, org_id=org.id, clerk_user_id=str(uuid4()))
        
        res_kw = await get_regulation_requirements(
            id=reg.id, search="consent", page=1, size=10, db=db, user=mock_user
        )
        assert res_kw.total >= 2, f"Expected at least 2 consent results, got {res_kw.total}"
        logger.info(f"Query: 'consent' -> Found {res_kw.total} results.")
        for idx, item in enumerate(res_kw.items):
            logger.info(f"  Rank {idx+1}: [{item.title}] (Score: {item.search_score})")
            
        assert res_kw.items[0].id in [req_consent_1.id, req_consent_2.id], "Top result should be a consent requirement!"
        logger.info("PASS: Keyword search correctly ranked relevant results.")
        
        # Test 2: Similar Requirements Panel endpoint
        logger.info("\n--- TEST 2: Similar Requirements Panel (pgvector nearest neighbors) ---")
        from app.api.routers.requirements import get_similar_requirements
        sim_res = await get_similar_requirements(id=req_consent_1.id, db=db, user=mock_user)
        assert len(sim_res) > 0, "Expected similar requirements for req_consent_1"
        logger.info(f"Target Requirement: '{req_consent_1.title}' -> Found {len(sim_res)} neighbors:")
        for idx, neighbor in enumerate(sim_res):
            logger.info(f"  Neighbor {idx+1}: [{neighbor.title}] - Match Score: {neighbor.similarity_score * 100:.1f}%")
            
        assert sim_res[0].title in [req_consent_2.title, req_consent_1.title], f"Expected a consent requirement as top neighbor, got '{sim_res[0].title}'"
        assert any(n.id == req_consent_2.id for n in sim_res), "Expected req_consent_2 in top neighbors!"
        assert sim_res[0].similarity_score > 0.8, f"Expected high similarity score > 0.8, got {sim_res[0].similarity_score}"
        logger.info("PASS: Similar requirements endpoint returned correct semantic neighbor!")
        
        # Test 3: General search endpoint search_all_requirements
        logger.info("\n--- TEST 3: General Requirements Search Endpoint ---")
        from app.api.routers.requirements import search_all_requirements
        gen_res = await search_all_requirements(search="marketing", limit=5, db=db, user=mock_user)
        assert len(gen_res) > 0, "Expected results for general search 'marketing'"
        logger.info(f"General Query: 'marketing' -> Top match: '{gen_res[0].title}' (Score: {gen_res[0].search_score})")
        assert gen_res[0].title == req_consent_2.title, f"Expected '{req_consent_2.title}' as top result, got '{gen_res[0].title}'"
        logger.info("PASS: General search endpoint correctly matched and ranked requirement.")
        
        logger.info("\n=======================================================")
        logger.info("PHASE 13 END-TO-END VERIFICATION SUCCESSFUL (ALL PASS)")
        logger.info("=======================================================")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_tests())
