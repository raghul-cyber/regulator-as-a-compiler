import asyncio
import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from alembic.config import Config
from alembic import command
from app.core.config import settings
from sqlalchemy import text

TEST_DB_NAME = "rac_db_test_migrations"

async def create_test_db():
    # Connect to the default db to create the test db
    default_url = str(settings.DATABASE_URL).replace("/rac_db", "/postgres")
    engine = create_async_engine(default_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    await engine.dispose()

async def drop_test_db():
    default_url = str(settings.DATABASE_URL).replace("/rac_db", "/postgres")
    engine = create_async_engine(default_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)"))
    await engine.dispose()

def run_alembic_upgrade():
    alembic_cfg = Config("alembic.ini")
    # override database url
    test_url = str(settings.DATABASE_URL).replace("/rac_db", f"/{TEST_DB_NAME}")
    alembic_cfg.set_main_option("sqlalchemy.url", test_url)
    command.upgrade(alembic_cfg, "head")

def run_alembic_downgrade():
    alembic_cfg = Config("alembic.ini")
    test_url = str(settings.DATABASE_URL).replace("/rac_db", f"/{TEST_DB_NAME}")
    alembic_cfg.set_main_option("sqlalchemy.url", test_url)
    command.downgrade(alembic_cfg, "base")

def test_migrations_upgrade_downgrade():
    asyncio.run(create_test_db())
    try:
        # Run upgrade
        run_alembic_upgrade()
        # Verify if upgrade passes cleanly (if it doesn't, an exception is raised)
        
        # Run downgrade
        run_alembic_downgrade()
    finally:
        asyncio.run(drop_test_db())
