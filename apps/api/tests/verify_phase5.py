import asyncio
import json
from unittest.mock import patch, AsyncMock
from uuid import uuid4
from datetime import datetime, timezone
import time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.requirements import Requirement, RequirementType, Severity, ValidationStatus, RequirementEmbedding
from app.models.llm_logs import LLMCallLog
from app.models.documents import SourceDocument, DocumentSection
from app.models.organizations import Organization
from app.pipelines.llm_extraction import extract_requirements, classify_chunk, ExtractionResult, ExtractedRequirement, ClassificationResult
from app.pipelines.dedup import deduplicate_requirements, persist_embeddings
from app.core.config import settings

async def run_tests():
    print("--- Phase 5 Verification (MOCKED) ---")
    
    # 4. Force Schema Validation Failure & Retry Loop
    # We will patch openai to fail once with bad json, then succeed
    call_count = 0
    
    async def mock_parse_retry(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Mocked Schema ValidationError")
        
        # Second call succeeds
        class MockChoice:
            def __init__(self, parsed):
                self.message = type("MockMsg", (), {"parsed": parsed})
        class MockResponse:
            def __init__(self, parsed):
                self.choices = [MockChoice(parsed)]
                self.usage = type("MockUsage", (), {"prompt_tokens": 100, "completion_tokens": 50})
        
        req_format = kwargs.get("response_format")
        if req_format == ClassificationResult:
            return MockResponse(ClassificationResult(has_requirements=True))
        elif req_format == ExtractionResult:
            reqs = [
                ExtractedRequirement(type="obligation", title="Data Minimisation", description="Personal data shall be adequate, relevant and limited to what is necessary in relation to the purposes for which they are processed.", conditions=[], actions=["Limit data processing"], severity="high", evidence_required=[], references=["Article 5(1)(c)"])
            ]
            return MockResponse(ExtractionResult(requirements=reqs))

    with patch("app.pipelines.llm_extraction.client.beta.chat.completions.parse", new_callable=AsyncMock, side_effect=mock_parse_retry):
        async with AsyncSessionLocal() as db:
            print("\n4. Forcing Schema Validation Failure...")
            try:
                # The retry loop in llm_extraction.py should catch the first error and succeed on second try
                extracted = await extract_requirements("Article 5 Data Minimisation", db)
                print(f"   Retry Loop Success. Extracted: {len(extracted)} requirements after {call_count} API calls (1st failed, 2nd succeeded).")
                
                # Verify llm_call_logs captured this
                logs = (await db.execute(select(LLMCallLog).order_by(LLMCallLog.created_at.desc()).limit(2))).scalars().all()
                print("\n5. Confirm llm_call_logs Row Population:")
                for log in logs:
                    print(f"   Log ID: {log.id}, Stage: {log.pipeline_stage}, Model: {log.model_used}, Tokens (P/C): {log.prompt_tokens}/{log.completion_tokens}, Latency: {log.latency_ms}ms, Cost: ${log.cost_usd:.5f}")

            except Exception as e:
                print(f"   Retry Loop Failed unexpectedly: {e}")

    # 6. Deduplication via Embedding Similarity
    async def mock_embeddings_create(*args, **kwargs):
        class MockResponse:
            def __init__(self):
                # Return the exact same vector for any input to simulate 100% similarity
                self.data = [type("Data", (), {"embedding": [0.1] * 1536})()]
                self.usage = type("MockUsage", (), {"prompt_tokens": 20})
        return MockResponse()

    print("\n6. Confirm Dedup correctly flags duplicated requirement...")
    with patch("app.pipelines.dedup.client.embeddings.create", new_callable=AsyncMock, side_effect=mock_embeddings_create):
        async with AsyncSessionLocal() as db:
            org = (await db.execute(select(Organization))).scalars().first()
            if not org:
                org = Organization(id=uuid4(), name="Test", plan="standard")
                db.add(org)
                await db.flush()

            from app.models.regulations import Regulation, RegulationVersion
            from app.models.documents import DocumentSection, SourceDocument, FileType
            from datetime import date
            # Create FK dependencies
            reg = Regulation(id=uuid4(), name="GDPR", jurisdiction="EU", source_url="http")
            db.add(reg)
            await db.flush()
            reg_ver = RegulationVersion(id=uuid4(), regulation_id=reg.id, version_label="1", published_date=date.today(), ingested_at=datetime.now())
            db.add(reg_ver)
            await db.flush()
            doc = SourceDocument(id=uuid4(), regulation_version_id=reg_ver.id, file_type=FileType.pdf, storage_path="x", raw_text="...", ocr_used=False, page_count=1)
            db.add(doc)
            await db.flush()
            section = DocumentSection(id=uuid4(), source_document_id=doc.id, order_index=1, reference_label="Art 5", raw_text="...")
            db.add(section)
            await db.flush()

            # Create an original requirement and flush it to give it an ID
            original = Requirement(id=uuid4(), regulation_version_id=reg_ver.id, section_id=section.id, title="Test Original", description="This is a test", severity=Severity.low, type=RequirementType.obligation, conditions={}, actions={}, evidence_required={}, references={}, confidence_score=0.99, validation_status=ValidationStatus.draft)
            db.add(original)
            await db.flush()
            
            # Persist its embedding (using the mock function directly)
            from app.pipelines.dedup import generate_embedding
            embed = await generate_embedding("Test Original", db)
            original._embedding_vector = embed
            await persist_embeddings([original], db)
            await db.commit()

            # Now try to deduplicate a new requirement that should get the exact same embedding
            new_req = Requirement(id=uuid4(), regulation_version_id=reg_ver.id, section_id=section.id, title="Test Original", description="This is a test", severity=Severity.low, type=RequirementType.obligation, conditions={}, actions={}, evidence_required={}, references={}, confidence_score=0.99, validation_status=ValidationStatus.draft)
            unique = await deduplicate_requirements([new_req], db, threshold=0.95)
            
            if len(unique) == 0:
                print("   PASS: The duplicated requirement was correctly flagged and dropped via embedding similarity (< 0.05 distance).")
            else:
                print("   FAIL: The duplicated requirement was NOT dropped.")

if __name__ == "__main__":
    asyncio.run(run_tests())
