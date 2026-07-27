import pytest
import pytest_asyncio
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException
import httpx
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.main import app as main_app
from app.models.users import User, UserRole
from app.models.organizations import Organization
from app.models.base import Base
from app.core.auth import require_role, get_current_user

from sqlalchemy.pool import NullPool

# Test database URL (same as used in test_migrations.py)
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/rac_db_test_migrations"

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    # Ensure tables exist
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
async def seed_data(db_session: AsyncSession):
    org_a_id = uuid4()
    org_b_id = uuid4()
    
    org_a = Organization(id=org_a_id, name="Org A", plan="standard")
    org_b = Organization(id=org_b_id, name="Org B", plan="standard")
    
    db_session.add_all([org_a, org_b])
    
    # Org A Users
    admin_a = User(id=uuid4(), org_id=org_a_id, clerk_user_id="clerk_a1", role=UserRole.admin, email="admin@orga.com")
    member_a = User(id=uuid4(), org_id=org_a_id, clerk_user_id="clerk_a2", role=UserRole.developer, email="dev@orga.com")
    
    # Org B Users
    admin_b = User(id=uuid4(), org_id=org_b_id, clerk_user_id="clerk_b1", role=UserRole.admin, email="admin@orgb.com")
    member_b = User(id=uuid4(), org_id=org_b_id, clerk_user_id="clerk_b2", role=UserRole.compliance_officer, email="comp@orgb.com")
    
    db_session.add_all([admin_a, member_a, admin_b, member_b])
    await db_session.commit()
    
    return {
        "org_a": org_a_id,
        "org_b": org_b_id,
        "admin_a": admin_a,
        "member_a": member_a,
        "admin_b": admin_b,
        "member_b": member_b,
    }

@pytest.mark.asyncio
async def test_org_scoping_and_roles(seed_data, db_session: AsyncSession):
    # Override get_db to return our test session
    from app.db.session import get_db
    main_app.dependency_overrides[get_db] = lambda: db_session
    
    async with httpx.AsyncClient(transport=ASGITransport(app=main_app), base_url="http://test") as client:
        # Test 1: Admin in Org A can fetch users, but only sees Org A users
        main_app.dependency_overrides[get_current_user] = lambda: seed_data["admin_a"]
        
        res = await client.get("/api/org/users")
        assert res.status_code == 200
        users = res.json()
        assert len(users) == 2
        for u in users:
            assert u["org_id"] == str(seed_data["org_a"])
            
        # Test 2: Developer in Org A cannot access the endpoint (Role Matrix: Admin only)
        main_app.dependency_overrides[get_current_user] = lambda: seed_data["member_a"]
        res = await client.get("/api/org/users")
        assert res.status_code == 403
        
        # Test 3: Admin A trying to remove Member B (Cross-tenant attempt)
        main_app.dependency_overrides[get_current_user] = lambda: seed_data["admin_a"]
        res = await client.delete(f"/api/org/users/{seed_data['member_b'].id}")
        assert res.status_code == 404 # 404 because BaseRepository filters out Org B items
        
        # Test 4: Admin A can remove Member A
        res = await client.delete(f"/api/org/users/{seed_data['member_a'].id}")
        assert res.status_code == 204
        
        # Verify Member A is gone
        res = await client.get("/api/org/users")
        assert len(res.json()) == 1
        assert res.json()[0]["id"] == str(seed_data["admin_a"].id)
