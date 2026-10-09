"""Authenticated PostgreSQL integration tests; isolated schemas, no model mocks."""
from datetime import date, timedelta
from decimal import Decimal
import threading

from alembic import command
import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.models import Sale, User
from app.ml import service
from tests.test_migrations import migration_connection, migrate
from tests.test_uploads import authenticated

ENDPOINT = "/api/v1/predictions"


@pytest_asyncio.fixture
async def db_session(migration_connection):
    await migration_connection.run_sync(migrate, command.upgrade, "head")
    async with AsyncSession(
        bind=migration_connection, expire_on_commit=False, autoflush=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session


async def add_history(db, shop=101, sku="Apple", days=42, units="12.75", start=date(2026, 1, 1)):
    db.add_all([
        Sale(shop_id=shop, sku_name=sku, date=start + timedelta(days=i), num_units_sold=Decimal(units))
        for i in range(days)
    ])
    await db.commit()


async def test_forecast_contract_and_real_regression(client, authenticated, db_session):
    await add_history(db_session)
    response = await client.post(ENDPOINT, headers=authenticated[1])
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok", "forecast_date": "2026-02-12", "total": 1,
        "training_rows": 14, "items": [{"sku_name": "Apple", "predicted_units": 13}],
        "skipped": [], "warnings": [],
    }


@pytest.mark.parametrize("token", [None, "invalid", "expired"])
async def test_requires_existing_jwt_dependency(client, token):
    if token == "expired":
        token = create_access_token(42, expires_delta=timedelta(seconds=-1))
    response = await client.post(ENDPOINT, headers={"Authorization": f"Bearer {token}"} if token else {})
    assert response.status_code == 401


async def test_forecast_shop_isolation_includes_training_and_latest_date(client, authenticated, db_session):
    await add_history(db_session)
    initial = (await client.post(ENDPOINT, headers=authenticated[1])).json()
    await add_history(db_session, shop=102, units="999999.00", start=date(2027, 1, 1))
    await add_history(db_session, shop=102, sku="Other-only", units="500000.00", start=date(2027, 1, 1))
    token = create_access_token(authenticated[0], extra_claims={"shop_id": 102})
    response = await client.post(
        ENDPOINT, headers={"Authorization": f"Bearer {token}"},
        params={"shop_id": 102}, json={"shop_id": 102},
    )
    assert response.status_code == 200
    assert response.json() == initial


async def test_database_shop_reassignment_is_authoritative(client, authenticated, db_session):
    await add_history(db_session, units="10")
    await add_history(db_session, shop=102, units="99")
    user = await db_session.get(User, authenticated[0])
    user.shop_id = 102
    await db_session.commit()
    db_session.expunge_all()
    response = await client.post(ENDPOINT, headers=authenticated[1])
    assert response.status_code == 200
    assert response.json()["items"] == [{"sku_name": "Apple", "predicted_units": 99}]


async def test_no_shop_sales_even_when_another_shop_has_training(client, authenticated, db_session):
    await add_history(db_session, shop=102)
    response = await client.post(ENDPOINT, headers=authenticated[1])
    assert response.status_code == 200
    assert response.json() == {
        "status": "no_sales", "forecast_date": None, "items": [], "total": 0,
        "training_rows": 0, "skipped": [], "warnings": [],
    }


async def test_another_shops_history_cannot_supply_training(client, authenticated, db_session):
    await add_history(db_session, days=28)
    await add_history(db_session, shop=102)
    response = await client.post(ENDPOINT, headers=authenticated[1])
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_history"
    assert response.json()["training_rows"] == 0
    assert response.json()["skipped"][0]["reason"] == "insufficient_training_data"


async def test_incomplete_history_reports_skipped_sku(client, authenticated, db_session):
    await add_history(db_session)
    await add_history(db_session, sku="Short", days=5)
    response = await client.post(ENDPOINT, headers=authenticated[1])
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["skipped"][0]["sku_name"] == "Short"
    assert response.json()["skipped"][0]["reason"] == "incomplete_history"


async def test_no_writes_and_shop_predicate_applied_in_database(client, authenticated, db_session):
    await add_history(db_session)
    before = (await db_session.execute(select(Sale.__table__).order_by(Sale.id))).all()
    connection = (await db_session.connection()).sync_connection
    statements = []
    def capture(_conn, _cursor, statement, parameters, _context, _many):
        statements.append((statement, parameters))
    event.listen(connection, "before_cursor_execute", capture)
    try:
        response = await client.post(ENDPOINT, headers=authenticated[1])
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert all(sql.lstrip().upper().startswith("SELECT") for sql, _ in statements)
    sales_queries = [(sql, parameters) for sql, parameters in statements if "FROM sales" in sql]
    assert len(sales_queries) == 1
    sql, parameters = sales_queries[0]
    assert "WHERE sales.shop_id =" in sql
    assert parameters == (101,)
    assert (await db_session.execute(select(Sale.__table__).order_by(Sale.id))).all() == before


async def test_feature_engineering_and_fit_run_off_event_loop(client, authenticated, db_session, monkeypatch):
    await add_history(db_session)
    event_loop_thread = threading.get_ident()
    compute = service._forecast_rows
    worker_threads = []
    def tracked(rows):
        worker_threads.append(threading.get_ident())
        return compute(rows)
    monkeypatch.setattr(service, "_forecast_rows", tracked)
    response = await client.post(ENDPOINT, headers=authenticated[1])
    assert response.status_code == 200
    assert len(worker_threads) == 1 and worker_threads[0] != event_loop_thread


async def test_unforecastable_date_has_clear_422(client, authenticated, db_session):
    await add_history(db_session, days=1, start=date.max)
    response = await client.post(ENDPOINT, headers=authenticated[1])
    assert response.status_code == 422
    assert "date" in response.json()["detail"]
