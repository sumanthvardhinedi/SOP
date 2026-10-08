"""Real PostgreSQL tests for sales retrieval, filters, and shop authorization."""
from datetime import date, timedelta
from decimal import Decimal

from alembic import command
import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.db.models import Sale, User
from tests.test_migrations import migration_connection, migrate
from tests.test_uploads import authenticated

ENDPOINT = "/api/v1/sales"


@pytest_asyncio.fixture
async def db_session(migration_connection):
    """Use a temporary schema and rolled-back transaction for every test."""
    await migration_connection.run_sync(migrate, command.upgrade, "head")
    async with AsyncSession(
        bind=migration_connection, expire_on_commit=False, autoflush=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session


@pytest_asyncio.fixture
async def sales(db_session):
    # Deliberately unsorted dates; same-day insertion order differs from SKU order.
    values = [
        (101, "2026-10-03", "Apple", "30.25"),
        (101, "2026-10-01", "Banana", "0.25"),
        (101, "2026-10-01", "Apple", "20.50"),
        (101, "2026-10-02", "Apple", "9999999999.99"),
        (101, "2026-10-02", "apple", "5.00"),
        (101, "2026-10-02", "ApplePie", "7.00"),
        (101, "2026-10-04", " Apple ", "1.25"),
        (102, "2026-10-01", "Apple", "999.00"),
        (102, "2026-10-02", "Other", "9.00"),
        (102, "2026-10-03", "Banana", "88.00"),
    ]
    records = [Sale(shop_id=shop, date=date.fromisoformat(day), sku_name=sku, num_units_sold=Decimal(units))
               for shop, day, sku, units in values]
    db_session.add_all(records)
    await db_session.commit()
    ids = [row.id for row in records]
    db_session.expunge_all()
    return ids


async def test_returns_only_own_shop_with_deterministic_order_and_contract(client, authenticated, sales):
    response = await client.get(ENDPOINT, headers=authenticated[1])
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"items", "total"}
    assert data["total"] == len(data["items"]) == 7
    assert [row["id"] for row in data["items"]] == [sales[i] for i in [1, 2, 3, 4, 5, 0, 6]]
    for row in data["items"]:
        assert set(row) == {"id", "date", "shop_id", "sku_name", "num_units_sold"}
        assert row["shop_id"] == 101
    assert data["items"][1]["num_units_sold"] == "20.50"
    assert data["items"][2]["num_units_sold"] == "9999999999.99"


@pytest.mark.parametrize("params,expected", [
    ({"start_date": "2026-10-02"}, [3, 4, 5, 0, 6]),
    ({"end_date": "2026-10-02"}, [1, 2, 3, 4, 5]),
    ({"sku_name": "Apple"}, [2, 3, 0]),
    ({"sku_name": "apple"}, [4]),
    ({"sku_name": " Apple "}, [6]),
    ({"start_date": "2026-10-01", "end_date": "2026-10-02", "sku_name": "Apple"}, [2, 3]),
    ({"start_date": "2026-10-01", "end_date": "2026-10-01"}, [1, 2]),
], ids=["start-inclusive", "end-inclusive", "sku-exact", "sku-case", "sku-spaces", "combined", "same-day"])
async def test_database_filters(client, authenticated, sales, params, expected):
    response = await client.get(ENDPOINT, headers=authenticated[1], params=params)
    assert response.status_code == 200
    data = response.json()
    assert [row["id"] for row in data["items"]] == [sales[i] for i in expected]
    assert data["total"] == len(expected)
    assert all(row["shop_id"] == 101 for row in data["items"])


@pytest.mark.parametrize("params", [
    {"sku_name": "Missing"}, {"sku_name": "App%"}, {"sku_name": "Apple' OR 1=1 --"},
    {"start_date": "2027-01-01"}, {"end_date": "2025-12-31"},
])
async def test_empty_filtered_results(client, authenticated, sales, params):
    response = await client.get(ENDPOINT, headers=authenticated[1], params=params)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_shop_without_sales_returns_empty(client, authenticated):
    response = await client.get(ENDPOINT, headers=authenticated[1])
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_inverted_dates_rejected(client, authenticated):
    response = await client.get(ENDPOINT, headers=authenticated[1], params={
        "start_date": "2026-10-03", "end_date": "2026-10-01",
    })
    assert response.status_code == 422
    assert "start_date must be on or before end_date" in response.json()["detail"][0]["msg"]


@pytest.mark.parametrize("field", ["start_date", "end_date"])
@pytest.mark.parametrize("value", ["bad-date", "2026-02-30", ""])
async def test_invalid_dates_rejected(client, authenticated, field, value):
    response = await client.get(ENDPOINT, headers=authenticated[1], params={field: value})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", field]


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
async def test_blank_sku_rejected(client, authenticated, value):
    response = await client.get(ENDPOINT, headers=authenticated[1], params={"sku_name": value})
    assert response.status_code == 422
    assert "sku_name must not be blank" in response.json()["detail"][0]["msg"]


@pytest.mark.parametrize("token", [None, "invalid", "expired"])
async def test_authentication_required(client, sales, token):
    if token == "expired":
        token = create_access_token(42, expires_delta=timedelta(seconds=-1))
    response = await client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"} if token else {})
    assert response.status_code == 401


@pytest.mark.parametrize("shop_id", ["102", "invalid", "-1"])
async def test_query_shop_id_is_ignored(client, authenticated, sales, shop_id):
    response = await client.get(ENDPOINT, headers=authenticated[1], params={"shop_id": shop_id})
    assert response.status_code == 200
    assert response.json()["total"] == 7
    assert {row["shop_id"] for row in response.json()["items"]} == {101}


async def test_other_user_resolves_their_own_shop(client, authenticated, sales, db_session):
    user = User(name="Other Shop", email="other@example.com", password_hash=hash_password("OtherPassword!123"), shop_id=102)
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(user.id, extra_claims={"shop_id": 101})
    response = await client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"}, params={"shop_id": 101})
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["items"]] == sales[7:]
    assert {row["shop_id"] for row in response.json()["items"]} == {102}


async def test_shop_assignment_is_loaded_from_database(client, authenticated, sales, db_session):
    user_id, _ = authenticated
    token = create_access_token(user_id, extra_claims={"shop_id": 101})
    user = await db_session.get(User, user_id)
    user.shop_id = 102
    await db_session.commit()
    db_session.expunge_all()
    response = await client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"}, params={"shop_id": 101})
    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert {row["shop_id"] for row in response.json()["items"]} == {102}


async def test_retrieval_executes_only_reads_and_filters_in_sql(client, authenticated, sales, db_session):
    before = (await db_session.execute(select(Sale.__table__).order_by(Sale.id))).all()
    connection = (await db_session.connection()).sync_connection
    statements = []

    def capture(_connection, _cursor, statement, parameters, _context, _executemany):
        statements.append((statement, parameters))

    event.listen(connection, "before_cursor_execute", capture)
    try:
        response = await client.get(ENDPOINT, headers=authenticated[1], params={
            "start_date": "2026-10-01", "end_date": "2026-10-02", "sku_name": "Apple",
        })
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert all(statement.lstrip().upper().startswith("SELECT") for statement, _ in statements)
    sales_queries = [(sql, values) for sql, values in statements if "FROM sales" in sql]
    assert len(sales_queries) == 1
    sql, parameters = sales_queries[0]
    assert "WHERE sales.shop_id =" in sql
    assert "sales.date >=" in sql and "sales.date <=" in sql and "sales.sku_name =" in sql
    assert set(parameters) == {101, date(2026, 10, 1), date(2026, 10, 2), "Apple"}
    assert (await db_session.execute(select(Sale.__table__).order_by(Sale.id))).all() == before
