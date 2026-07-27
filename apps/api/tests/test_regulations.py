import pytest
import pytest_asyncio
from uuid import uuid4
import httpx
from httpx import ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.pool import NullPool

from app.main import app as main_app
from app.models.base import Base
from app.models.users import User, UserRole
from app.models.organizations import Organization
from app.models.regulations import Regulation, RegulationVersion
from app.models.documents import SourceDocument

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

@pytest_asyncio.fixture
async def test_users(db_session: AsyncSession):
    org_id = uuid4()
    org = Organization(id=org_id, name="Test Org", plan="standard")
    
    admin_user = User(id=uuid4(), org_id=org_id, clerk_user_id="clerk_admin", role=UserRole.admin, email="admin@test.com")
    comp_user = User(id=uuid4(), org_id=org_id, clerk_user_id="clerk_comp", role=UserRole.compliance_officer, email="comp@test.com")
    dev_user = User(id=uuid4(), org_id=org_id, clerk_user_id="clerk_dev", role=UserRole.developer, email="dev@test.com")
    
    db_session.add_all([org, admin_user, comp_user, dev_user])
    await db_session.commit()
    
    return {
        "org_id": org_id,
        "admin": admin_user,
        "comp": comp_user,
        "dev": dev_user
    }

@pytest.mark.asyncio
async def test_regulation_upload_role_gating(test_users, db_session: AsyncSession):
    from app.db.session import get_db
    from app.core.auth import get_current_user
    
    main_app.dependency_overrides[get_db] = lambda: db_session
    
    async with httpx.AsyncClient(transport=ASGITransport(app=main_app), base_url="http://test") as client:
        # Developer should be rejected
        main_app.dependency_overrides[get_current_user] = lambda: test_users["dev"]
        
        files = {"file": ("test.pdf", b"dummy pdf content", "application/pdf")}
        data = {"jurisdiction": "US", "name": "Test Regulation"}
        
        res = await client.post("/api/regulations/upload", data=data, files=files)
        assert res.status_code == 403

@pytest.mark.asyncio
async def test_regulation_upload_invalid_file_type(test_users, db_session: AsyncSession):
    from app.db.session import get_db
    from app.core.auth import get_current_user
    
    main_app.dependency_overrides[get_db] = lambda: db_session
    main_app.dependency_overrides[get_current_user] = lambda: test_users["admin"]
    
    async with httpx.AsyncClient(transport=ASGITransport(app=main_app), base_url="http://test") as client:
        files = {"file": ("test.txt", b"dummy text", "text/plain")}
        data = {"jurisdiction": "US", "name": "Test Regulation"}
        
        res = await client.post("/api/regulations/upload", data=data, files=files)
        assert res.status_code == 400
        assert "Unsupported file type" in res.json()["detail"]

@pytest.mark.asyncio
async def test_regulation_upload_success_and_get(test_users, db_session: AsyncSession):
    from app.db.session import get_db
    from app.core.auth import get_current_user
    
    main_app.dependency_overrides[get_db] = lambda: db_session
    main_app.dependency_overrides[get_current_user] = lambda: test_users["comp"]
    
    async with httpx.AsyncClient(transport=ASGITransport(app=main_app), base_url="http://test") as client:
        files = {"file": ("test.pdf", b"dummy pdf content", "application/pdf")}
        data = {"jurisdiction": "US", "name": "Test Regulation"}
        
        # 1. Upload
        res = await client.post("/api/regulations/upload", data=data, files=files)
        assert res.status_code == 200
        body = res.json()
        reg_id = body["regulation_id"]
        
        # 2. Verify Get
        res_get = await client.get(f"/api/regulations/{reg_id}")
        assert res_get.status_code == 200
        assert res_get.json()["name"] == "Test Regulation"
        assert res_get.json()["jurisdiction"] == "US"
        assert res_get.json()["status"] == "processing"
        
        # 3. Verify Database
        stmt = select(Regulation).where(Regulation.id == reg_id)
        reg_res = await db_session.execute(stmt)
        reg = reg_res.scalar_one()
        assert reg.name == "Test Regulation"
        assert str(reg.current_version_id) == body["regulation_version_id"]
        
        stmt_docs = select(SourceDocument).where(SourceDocument.regulation_version_id == reg.current_version_id)
        docs_res = await db_session.execute(stmt_docs)
        doc = docs_res.scalar_one()
        assert doc.file_type == "pdf"
        assert "local://uploads" in doc.storage_path
