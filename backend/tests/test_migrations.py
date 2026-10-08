"""Exercise the real Alembic chain in isolated, transactional PostgreSQL schemas."""
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from fastapi.security import HTTPAuthorizationCredentials
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.schemas import UserLogin
from app.auth.service import authenticate_user
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import hash_password
from app.db.models import Base
from tests.test_schema import assert_database_schema


@pytest_asyncio.fixture
async def migration_connection():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                schema = f"migration_test_{uuid.uuid4().hex}"
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                yield connection
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


def migrate(connection, operation, target):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    config.attributes["connection"] = connection
    operation(config, target)


def assert_metadata_matches(connection):
    context = MigrationContext.configure(
        connection, opts={"compare_type": True, "compare_server_default": True}
    )
    assert compare_metadata(context, Base.metadata) == []


async def test_fresh_database_upgrade(migration_connection):
    await migration_connection.run_sync(migrate, command.upgrade, "head")
    await migration_connection.run_sync(assert_database_schema)
    await migration_connection.run_sync(assert_metadata_matches)


@pytest.mark.parametrize("stamp_existing", [False, True])
async def test_phase1_upgrade_preserves_users_sales_and_authentication(
    migration_connection, stamp_existing
):
    connection = migration_connection
    await connection.run_sync(migrate, command.upgrade, "0001_phase1_baseline")
    await connection.execute(text("INSERT INTO shops (id, name) VALUES (101, 'Example Shop')"))
    await connection.execute(
        text("""INSERT INTO users (name, email, password_hash, shop_id)
                VALUES ('Existing User', 'existing@example.com', :hash, 101)"""),
        {"hash": hash_password("ExistingPassword!123")},
    )
    await connection.execute(text("""
        INSERT INTO datasets (shop_id, uploaded_by, file_name, file_hash, file_type, file_size)
        SELECT 101, id, 'legacy.csv', repeat('a', 64), 'csv', 100 FROM users
    """))
    await connection.execute(text("""
        INSERT INTO sales (shop_id, dataset_id, date, product, quantity)
        SELECT 101, id, '2026-01-01', 'SKU001', 20.25 FROM datasets
    """))
    users_before = (await connection.execute(text("SELECT * FROM users ORDER BY id"))).all()
    sales_before = (await connection.execute(
        text("SELECT id, date, shop_id, product, quantity FROM sales ORDER BY id")
    )).all()
    if stamp_existing:
        # Simulate Phase 1 tables created before any revision was committed.
        await connection.execute(text("DROP TABLE alembic_version"))
        await connection.run_sync(migrate, command.stamp, "0001_phase1_baseline")

    await connection.run_sync(migrate, command.upgrade, "head")
    await connection.run_sync(assert_database_schema)
    await connection.run_sync(assert_metadata_matches)
    assert (await connection.execute(text("SELECT * FROM users ORDER BY id"))).all() == users_before
    assert (await connection.execute(
        text("SELECT id, date, shop_id, sku_name, num_units_sold FROM sales ORDER BY id")
    )).all() == sales_before
    assert (await connection.execute(text(
        "SELECT 1 FROM pg_type WHERE typname = 'dataset_status_enum' "
        "AND typnamespace = current_schema()::regnamespace"
    ))).first() is None

    async with AsyncSession(bind=connection) as session:
        token = await authenticate_user(
            session, UserLogin(email="existing@example.com", password="ExistingPassword!123")
        )
        user = await get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token.access_token), session
        )
        assert user.id == users_before[0].id
        assert user.shop_id == 101


async def test_downgrade_refuses_to_invent_removed_metadata(migration_connection):
    await migration_connection.run_sync(migrate, command.upgrade, "head")
    with pytest.raises(RuntimeError, match="Restore the pre-upgrade database backup"):
        await migration_connection.run_sync(migrate, command.downgrade, "0001_phase1_baseline")
    await migration_connection.run_sync(assert_database_schema)
    assert (await migration_connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == "0002_simplify_sales"
