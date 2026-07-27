import pytest
import pytest_asyncio
from uuid import uuid4
import os
import fitz
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.pool import NullPool

from app.models.base import Base
from app.models.organizations import Organization
from app.models.users import User, UserRole
from app.models.regulations import Regulation, RegulationVersion
from app.models.documents import SourceDocument, FileType, DocumentSection
from app.pipelines.extraction import extract_document_text
from app.pipelines.segmentation import segment_document
from datetime import date, datetime, timezone

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/rac_db_test_migrations"

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    async with TestingSessionLocal() as session:
        yield session
    await engine.dispose()

@pytest.fixture
def mock_pdf_path():
    path = "test_fixture.pdf"
    doc = fitz.open()
    page = doc.new_page()
    text = """Preamble text here that explains the regulation.
Article 1
General Provisions for the regulation.
Section 1.1
Specific sub-provisions.
Article 2
Definitions.
"""
    page.insert_text((50, 50), text)
    doc.save(path)
    doc.close()
    
    yield path
    
    if os.path.exists(path):
        os.remove(path)

@pytest.mark.asyncio
async def test_extraction_and_segmentation_pipeline(db_session: AsyncSession, mock_pdf_path: str):
    # Setup mock records
    org = Organization(id=uuid4(), name="Test Org", plan="standard")
    db_session.add(org)
    await db_session.flush()

    reg = Regulation(id=uuid4(), name="Test Reg", jurisdiction="US", source_url="")
    db_session.add(reg)
    await db_session.flush()
    
    reg_ver = RegulationVersion(
        id=uuid4(),
        regulation_id=reg.id,
        version_label="Draft",
        published_date=date(2026, 1, 1),
        ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    db_session.add(reg_ver)
    await db_session.flush()
    
    doc = SourceDocument(
        id=uuid4(),
        regulation_version_id=reg_ver.id,
        file_type=FileType.pdf,
        storage_path=f"local://{mock_pdf_path}",
        raw_text="",
        ocr_used=False,
        page_count=0
    )
    db_session.add(doc)
    await db_session.flush()
    
    reg_ver.source_document_id = doc.id
    await db_session.commit()

    # 1. Test Extraction
    extracted_text = await extract_document_text(doc.id, db_session)
    assert extracted_text is not None
    assert "Article 1" in extracted_text
    
    # Reload doc to check updates
    await db_session.refresh(doc)
    assert doc.raw_text == extracted_text
    assert doc.page_count == 1
    
    # 2. Test Segmentation
    section_count = await segment_document(doc.id, db_session)
    assert section_count > 0
    
    # Verify sections
    stmt = select(DocumentSection).where(DocumentSection.source_document_id == doc.id).order_by(DocumentSection.order_index)
    res = await db_session.execute(stmt)
    sections = res.scalars().all()
    
    assert len(sections) == 4
    assert sections[0].reference_label == "Preamble"
    assert sections[1].reference_label == "Article 1"
    assert sections[2].reference_label == "Section 1.1"
    assert sections[3].reference_label == "Article 2"
