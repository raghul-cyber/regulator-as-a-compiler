import pytest
import pytest_asyncio
import json
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.pipelines.llm_extraction import extract_requirements, classify_chunk

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/rac_db_test_migrations"

@pytest.fixture
def golden_dataset():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "gdpr_golden.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    async with TestingSessionLocal() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_extraction_quality_regression(golden_dataset, db_session: AsyncSession):
    """
    Runs the LLM extraction pipeline against a golden dataset of GDPR articles.
    Fails the build if the AI fails to extract the expected obligations.
    """
    
    # We require the OpenAI API key to be set. If not, skip or fail.
    # We assume it is set in CI/CD.
    from app.core.config import settings
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "sk-placeholder":
        pytest.skip("Skipping golden dataset test because OPENAI_API_KEY is not configured.")
    
    for case in golden_dataset:
        text = case["text"]
        expected_reqs = case["expected_requirements"]
        
        # 1. Classification
        has_reqs = await classify_chunk(text, db_session)
        assert has_reqs is True, f"Failed to classify requirements in: {text[:50]}"
        
        # 2. Extraction
        extracted = await extract_requirements(text, db_session)
        
        # Verify we got at least as many requirements as expected
        assert len(extracted) >= len(expected_reqs), f"Expected {len(expected_reqs)} requirements, got {len(extracted)}"
        
        # Check that types and severities roughly match
        # (This is a simplified regression test; a true golden test would map cosine similarity of embeddings)
        for expected in expected_reqs:
            found = any(
                req.type.value == expected["type"] and req.severity.value == expected["severity"]
                for req in extracted
            )
            assert found is True, f"Missing expected requirement: {expected} in extractions: {extracted}"
