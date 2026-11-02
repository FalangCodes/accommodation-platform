"""Actual revision bodies on fresh disposable schemas; production DDL untouched."""
import re
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
import app.db.models
from app.db.base import Base
from app.core.config import settings


@pytest_asyncio.fixture
async def fresh_schema():
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://"), "Run on Azure/PostGIS"
    schema = "test_bootstrap_" + uuid.uuid4().hex
    assert re.fullmatch(r"test_bootstrap_[0-9a-f]{32}", schema)
    admin = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with admin.begin() as db:
        await db.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool,
        connect_args={"server_settings": {"search_path": f"{schema},public"}})
    try:
        yield engine, schema
    finally:
        await engine.dispose()
        async with admin.begin() as db:
            await db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


def revisions():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    return list(reversed(list(scripts.walk_revisions())))


@pytest.mark.asyncio
async def test_complete_forward_history_builds_current_application_schema(fresh_schema):
    engine, schema = fresh_schema
    async with engine.begin() as db:
        assert (await db.execute(text("SELECT current_schema()"))).scalar_one() == schema
        oid = (await db.execute(text("SELECT 'public.spatial_ref_sys'::regclass::oid"))).scalar_one()
        def upgrade(sync):
            with Operations.context(MigrationContext.configure(sync)):
                for revision in revisions():
                    revision.module.upgrade()
            inspector = inspect(sync)
            names = set(inspector.get_table_names(schema=schema))
            assert names == set(Base.metadata.tables) | {"moderation_queue"}
            for table in Base.metadata.sorted_tables:
                columns = {column["name"] for column in inspector.get_columns(table.name, schema=schema)}
                assert set(table.c.keys()).issubset(columns), (table.name, set(table.c.keys()) - columns)
        await db.run_sync(upgrade)
        assert (await db.execute(text("SELECT 'public.spatial_ref_sys'::regclass::oid"))).scalar_one() == oid


@pytest.mark.asyncio
async def test_base_rollback_never_recreates_postgis_owned_tables(fresh_schema):
    engine, schema = fresh_schema
    async with engine.begin() as db:
        assert (await db.execute(text("SELECT current_schema()"))).scalar_one() == schema
        oid = (await db.execute(text("SELECT 'public.spatial_ref_sys'::regclass::oid"))).scalar_one()
        def round_trip(sync):
            base = revisions()[0].module
            with Operations.context(MigrationContext.configure(sync)):
                base.upgrade()
                # No fallback to public while exercising destructive rollback.
                sync.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                base.downgrade()
            assert inspect(sync).get_table_names(schema=schema) == []
        await db.run_sync(round_trip)
        assert (await db.execute(text("SELECT 'public.spatial_ref_sys'::regclass::oid"))).scalar_one() == oid
