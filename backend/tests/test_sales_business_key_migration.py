"""Data-preserving upgrade/downgrade and duplicate refusal on PostgreSQL."""
from alembic import command
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from tests.test_migrations import migration_connection, migrate, assert_metadata_matches
from tests.test_schema import assert_database_schema


async def seed_sale(connection):
    await connection.execute(text("""
        INSERT INTO sales (shop_id, date, sku_name, num_units_sold)
        VALUES (101, '2026-10-01', 'Apple', 20.25)
    """))


async def test_unique_migration_upgrade_and_downgrade_preserve_rows(migration_connection):
    connection = migration_connection
    await connection.run_sync(migrate, command.upgrade, "0002_simplify_sales")
    await seed_sale(connection)
    before = (await connection.execute(text("SELECT * FROM sales"))).all()
    await connection.run_sync(migrate, command.upgrade, "head")
    await connection.run_sync(assert_database_schema)
    await connection.run_sync(assert_metadata_matches)
    constraints = await connection.run_sync(lambda conn: inspect(conn).get_unique_constraints("sales"))
    assert any(c["column_names"] == ["shop_id", "date", "sku_name"] for c in constraints)
    assert (await connection.execute(text("SELECT * FROM sales"))).all() == before
    await connection.run_sync(migrate, command.downgrade, "0002_simplify_sales")
    assert (await connection.execute(text("SELECT * FROM sales"))).all() == before
    assert await connection.run_sync(lambda conn: inspect(conn).get_unique_constraints("sales")) == []
    await connection.run_sync(migrate, command.upgrade, "head")
    await connection.run_sync(assert_metadata_matches)


async def test_unique_migration_refuses_duplicates_without_deleting_data(migration_connection):
    connection = migration_connection
    await connection.run_sync(migrate, command.upgrade, "0002_simplify_sales")
    await seed_sale(connection)
    await seed_sale(connection)
    before = (await connection.execute(text("SELECT * FROM sales ORDER BY id"))).all()
    # Simulate the CLI's failed migration transaction within this test's outer one.
    with pytest.raises(DBAPIError, match="duplicate .* records exist"):
        async with connection.begin_nested():
            await connection.run_sync(migrate, command.upgrade, "head")
    assert (await connection.execute(text("SELECT * FROM sales ORDER BY id"))).all() == before
    assert (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == "0002_simplify_sales"
    assert await connection.run_sync(lambda conn: inspect(conn).get_unique_constraints("sales")) == []
