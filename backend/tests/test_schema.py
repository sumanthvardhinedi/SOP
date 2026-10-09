"""Model and PostgreSQL enforcement of the simplified application schema."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import Date, Integer, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Base, Sale


EXPECTED_COLUMNS = {
    "users": {"id", "name", "email", "password_hash", "shop_id", "created_at", "updated_at"},
    "sales": {"id", "date", "shop_id", "sku_name", "num_units_sold"},
}


def assert_database_schema(connection) -> None:
    inspector = inspect(connection)
    assert set(inspector.get_table_names()) == {"alembic_version", "users", "sales"}
    for table, columns in EXPECTED_COLUMNS.items():
        assert {column["name"] for column in inspector.get_columns(table)} == columns
        assert inspector.get_foreign_keys(table) == []
    sales_columns = {column["name"]: column for column in inspector.get_columns("sales")}
    assert isinstance(sales_columns["date"]["type"], Date)
    assert isinstance(sales_columns["shop_id"]["type"], Integer)
    assert all(not column["nullable"] for column in sales_columns.values())
    sales_indexes = {tuple(index["column_names"]) for index in inspector.get_indexes("sales")}
    assert {("shop_id",), ("date",), ("sku_name",), ("shop_id", "date")} <= sales_indexes
    assert any(
        index["unique"] and index["column_names"] == ["email"]
        for index in inspector.get_indexes("users")
    )


def test_only_user_and_sale_models() -> None:
    assert set(Base.metadata.tables) == set(EXPECTED_COLUMNS)
    for table, columns in EXPECTED_COLUMNS.items():
        assert set(Base.metadata.tables[table].columns.keys()) == columns
        assert not Base.metadata.tables[table].foreign_keys


async def test_migrated_database_schema(db_session: AsyncSession) -> None:
    connection = await db_session.connection()
    await connection.run_sync(assert_database_schema)


@pytest.mark.parametrize("units", [Decimal("0"), Decimal("20"), Decimal("1.25")])
async def test_sales_accept_valid_business_data(db_session: AsyncSession, units: Decimal) -> None:
    sale = Sale(date=date(2026, 1, 1), shop_id=101, sku_name="SKU001", num_units_sold=units)
    db_session.add(sale)
    await db_session.commit()
    await db_session.refresh(sale)
    assert sale.num_units_sold == units
    assert sale.date == date(2026, 1, 1)


@pytest.mark.parametrize(
    "sku_name, units",
    [("", 1), ("   ", 1), ("SKU001", -1), (None, 1), ("SKU001", None)],
)
async def test_sales_reject_invalid_business_data(
    db_session: AsyncSession, sku_name: str | None, units: int | None
) -> None:
    db_session.add(Sale(date=date(2026, 1, 1), shop_id=101, sku_name=sku_name, num_units_sold=units))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
