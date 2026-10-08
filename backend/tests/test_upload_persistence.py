"""Phase 3B HTTP and real PostgreSQL upsert/transaction regression tests."""
import asyncio
from datetime import date
from decimal import Decimal
import uuid

from alembic import command
import pytest
import pytest_asyncio
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import Sale, User
from app.uploads import persistence
from app.uploads.persistence import persist_sales
from app.uploads.schemas import ValidatedSale
from tests.test_migrations import migration_connection, migrate
from tests.test_uploads import authenticated, workbook_bytes, VALID_ROW, XLSX_MIME

ENDPOINT = "/api/v1/sales/upload"


@pytest_asyncio.fixture
async def db_session(migration_connection):
    """Isolate every persistence test from existing development users and sales."""
    await migration_connection.run_sync(migrate, command.upgrade, "head")
    async with AsyncSession(
        bind=migration_connection, expire_on_commit=False, autoflush=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session


async def upload(client, headers, rows, *, filename="sales.xlsx", extra_query="", data=None):
    return await client.post(
        ENDPOINT + extra_query, headers=headers, data=data,
        files={"file": (filename, workbook_bytes(rows), XLSX_MIME)},
    )


async def sales_snapshot(db):
    return (await db.execute(select(Sale.__table__).order_by(Sale.id))).all()


async def test_new_sales_and_multiple_rows(client, authenticated, db_session):
    response = await upload(client, authenticated[1], [
        VALID_ROW, [101, "Banana", 0.25, "2026-10-01"], [101, "Apple", 25, "2026-10-02"],
    ])
    assert response.status_code == 200
    assert response.json() == {"success": True, "row_count": 3, "inserted_count": 3, "updated_count": 0}
    rows = await sales_snapshot(db_session)
    assert {(row.shop_id, row.date, row.sku_name, row.num_units_sold) for row in rows} == {
        (101, date(2026, 10, 1), "Apple", Decimal("20")),
        (101, date(2026, 10, 1), "Banana", Decimal("0.25")),
        (101, date(2026, 10, 2), "Apple", Decimal("25")),
    }


@pytest.mark.parametrize("quantity", [25, 0, 0.25, 20])
async def test_update_replaces_not_adds_and_preserves_id(client, authenticated, db_session, quantity):
    await upload(client, authenticated[1], [VALID_ROW])
    before = await sales_snapshot(db_session)
    response = await upload(client, authenticated[1], [[101, "Apple", quantity, "2026-10-01"]])
    assert response.status_code == 200
    assert response.json() == {"success": True, "row_count": 1, "inserted_count": 0, "updated_count": 1}
    after = await sales_snapshot(db_session)
    assert len(after) == 1
    assert after[0].id == before[0].id
    assert after[0].num_units_sold == Decimal(str(quantity))


async def test_mixed_insert_update_and_other_shop_untouched(client, authenticated, db_session):
    await upload(client, authenticated[1], [VALID_ROW])
    db_session.add_all([
        Sale(shop_id=102, date=date(2026, 10, 1), sku_name="Apple", num_units_sold=90),
        Sale(shop_id=102, date=date(2026, 10, 1), sku_name="Banana", num_units_sold=80),
    ])
    await db_session.commit()
    other_before = [row for row in await sales_snapshot(db_session) if row.shop_id == 102]
    response = await upload(client, authenticated[1], [
        [101, "Apple", 25, "2026-10-01"], [101, "Banana", 15, "2026-10-01"],
    ])
    assert response.status_code == 200
    assert response.json() == {"success": True, "row_count": 2, "inserted_count": 1, "updated_count": 1}
    assert [row for row in await sales_snapshot(db_session) if row.shop_id == 102] == other_before


async def test_duplicate_key_rejected_with_original_excel_row_numbers(client, authenticated, db_session):
    response = await upload(client, authenticated[1], [
        VALID_ROW, [None] * 4, [101, "Apple", 25, date(2026, 10, 1)],
    ])
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["errors"] == [{
        "row": 4, "column": None,
        "message": "Duplicate (shop_id, date, sku_name); first appears at row 2.",
    }]
    assert await sales_snapshot(db_session) == []


@pytest.mark.parametrize("rows", [
    [[102, "Apple", 20, "2026-10-01"]],
    [VALID_ROW, [102, "Banana", 15, "2026-10-01"]],
    [VALID_ROW, [101, "Banana", -1, "2026-10-01"]],
    [VALID_ROW, [101, "Banana", 1, "bad-date"]],
    [VALID_ROW, VALID_ROW],
], ids=["wrong-shop", "mixed-shops", "negative-units", "invalid-date", "duplicate"])
async def test_invalid_upload_is_rejected_before_any_writes(client, authenticated, db_session, rows):
    db_session.add(Sale(shop_id=101, date=date(2026, 10, 1), sku_name="Apple", num_units_sold=7))
    await db_session.commit()
    before = await sales_snapshot(db_session)
    response = await upload(client, authenticated[1], rows)
    assert response.status_code == 422
    assert response.json()["detail"]["errors"]
    assert await sales_snapshot(db_session) == before


@pytest.mark.parametrize("filename", ["sales.csv", "sales.xls", "sales.txt"])
async def test_unsupported_type_rejected(client, authenticated, db_session, filename):
    response = await upload(client, authenticated[1], [VALID_ROW], filename=filename)
    assert response.status_code == 415
    assert response.json()["detail"]["success"] is False
    assert await sales_snapshot(db_session) == []


async def test_upload_requires_authentication(client, db_session):
    response = await upload(client, {}, [VALID_ROW])
    assert response.status_code == 401
    assert await sales_snapshot(db_session) == []


async def test_stored_shop_overrides_jwt_query_and_form(client, authenticated, db_session):
    user_id, _ = authenticated
    user = await db_session.get(User, user_id)
    user.shop_id = 102
    await db_session.commit()
    db_session.expunge_all()
    headers = {"Authorization": f"Bearer {create_access_token(user_id, extra_claims={'shop_id': 101})}"}
    response = await upload(client, headers, [VALID_ROW], extra_query="?shop_id=101", data={"shop_id": "101"})
    assert response.status_code == 422
    assert await sales_snapshot(db_session) == []
    response = await upload(client, headers, [[102, "Apple", 25, "2026-10-01"]])
    assert response.status_code == 200
    assert {row.shop_id for row in await sales_snapshot(db_session)} == {102}


async def test_database_error_rolls_back_prior_insert_and_update_batches(
    client, authenticated, db_session, monkeypatch
):
    db_session.add(Sale(shop_id=101, date=date(2026, 10, 1), sku_name="Apple", num_units_sold=7))
    await db_session.commit()
    before = await sales_snapshot(db_session)
    # Real PostgreSQL failure after a successful batch, not a mocked execute error.
    # The extra test-only check is rolled back by the outer fixture transaction.
    await db_session.execute(text("ALTER TABLE sales ADD CONSTRAINT test_reject_sku CHECK (sku_name <> 'ZZ_FAIL')"))
    await db_session.commit()
    monkeypatch.setattr(persistence, "UPSERT_BATCH_SIZE", 2)
    connection = (await db_session.connection()).sync_connection
    successful_writes = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("INSERT INTO sales"):
            successful_writes.append(statement)

    event.listen(connection, "after_cursor_execute", capture)
    try:
        response = await upload(client, authenticated[1], [
            [101, "Apple", 25, "2026-10-01"],
            [101, "Banana", 15, "2026-10-01"],
            [101, "ZZ_FAIL", 10, "2026-10-01"],
        ])
    finally:
        event.remove(connection, "after_cursor_execute", capture)
    assert len(successful_writes) == 1
    assert response.status_code == 500
    assert "rolled back" in response.json()["detail"]
    assert "test_reject_sku" not in response.text
    assert await sales_snapshot(db_session) == before


async def test_success_across_multiple_batches(client, authenticated, db_session, monkeypatch):
    monkeypatch.setattr(persistence, "UPSERT_BATCH_SIZE", 2)
    response = await upload(client, authenticated[1], [[101, f"SKU{i}", i, "2026-10-01"] for i in range(5)])
    assert response.status_code == 200
    assert response.json()["inserted_count"] == 5
    assert len(await sales_snapshot(db_session)) == 5


async def test_database_enforces_uniqueness(db_session):
    values = dict(shop_id=101, date=date(2026, 10, 1), sku_name="Apple", num_units_sold=20)
    db_session.add(Sale(**values))
    await db_session.commit()
    db_session.add(Sale(**values))
    with pytest.raises(IntegrityError, match="uq_sales_shop_id_date_sku_name"):
        await db_session.flush()
    await db_session.rollback()
    assert len(await sales_snapshot(db_session)) == 1


async def test_validate_remains_preview_only_including_duplicate_rows(client, authenticated, db_session):
    response = await client.post(ENDPOINT + "/validate", headers=authenticated[1], files={
        "file": ("sales.xlsx", workbook_bytes([VALID_ROW, VALID_ROW]), XLSX_MIME),
    })
    assert response.status_code == 200
    assert response.json()["row_count"] == 2
    assert await sales_snapshot(db_session) == []


async def test_concurrent_upserts_report_insert_and_update_without_duplicates():
    """Two genuine transactions on an isolated schema exercise ON CONFLICT races."""
    schema = f"concurrent_upload_{uuid.uuid4().hex}"
    admin = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool,
                                 connect_args={"server_settings": {"search_path": schema}})
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            await connection.run_sync(migrate, command.upgrade, "head")

        async def write(quantity):
            async with AsyncSession(engine) as db:
                return await persist_sales(db, [ValidatedSale(
                    shop_id=101, date=date(2026, 10, 1), sku_name="Apple", num_units_sold=quantity,
                )], 101)

        results = await asyncio.gather(write(20), write(25))
        assert sum(result.inserted_count for result in results) == 1
        assert sum(result.updated_count for result in results) == 1
        async with engine.connect() as connection:
            rows = (await connection.execute(select(Sale.__table__))).all()
            assert len(rows) == 1
            assert rows[0].num_units_sold in {Decimal(20), Decimal(25)}
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()
