"""Generated Excel fixtures for Phase 3A validation and its HTTP/auth boundary."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
import uuid
from zipfile import ZipFile, ZIP_DEFLATED

from openpyxl import Workbook
from openpyxl.utils.datetime import CALENDAR_MAC_1904
import pytest
import pytest_asyncio
from sqlalchemy import event, select

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import Sale, User
from app.uploads import parser
from app.uploads.schemas import SalesValidationError
from app.uploads.service import validate_sales_upload

HEADERS = ["shop_id", "sku_name", "num_units_sold", "date"]
VALID_ROW = [101, "Apple", 20, "2026-10-01"]
ENDPOINT = "/api/v1/sales/upload/validate"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def workbook_bytes(rows=(), headers=HEADERS, *, second_sheet=False, mac_dates=False):
    workbook = Workbook()
    if mac_dates:
        workbook.epoch = CALENDAR_MAC_1904
    if headers is not None:
        workbook.active.append(headers)
    for row in rows:
        workbook.active.append(row)
    if second_sheet:
        workbook.create_sheet("Other shop").append([102, "Hidden data"])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def validate(contents, filename="sales.xlsx"):
    return validate_sales_upload(contents, filename, 101)


def rewrite_member(contents, member, transform):
    output = BytesIO()
    with ZipFile(BytesIO(contents)) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for entry in source.infolist():
            data = source.read(entry.filename)
            target.writestr(entry, transform(data) if entry.filename == member else data)
    return output.getvalue()


def test_valid_xlsx_and_native_normalized_types():
    rows = validate(workbook_bytes([VALID_ROW, [101, "Banana", 0.25, datetime(2026, 10, 2, 13, 30)]]))
    assert len(rows) == 2
    assert rows[0].model_dump() == dict(zip(HEADERS, [101, "Apple", Decimal("20"), date(2026, 10, 1)]))
    assert rows[1].num_units_sold == Decimal("0.25")
    assert type(rows[1].date) is date
    assert rows[1].date == date(2026, 10, 2)


@pytest.mark.parametrize("filename", ["sales.csv", "sales.xls", "sales.json", "sales.txt", "sales", "sales.xlsx.csv", None])
def test_unsupported_extensions(filename):
    with pytest.raises(SalesValidationError) as error:
        validate(workbook_bytes([VALID_ROW]), filename)
    assert error.value.status_code == 415


@pytest.mark.parametrize("headers", [HEADERS[:-1], HEADERS + ["extra"], ["shop_id", "sku_name", "date", "date"], ["Shop_ID", *HEADERS[1:]]])
def test_missing_extra_duplicate_or_wrong_case_headers(headers):
    with pytest.raises(SalesValidationError) as error:
        validate(workbook_bytes([VALID_ROW], headers))
    assert error.value.errors[0].row == 1
    assert "exactly" in error.value.errors[0].message


@pytest.mark.parametrize("contents", [b"", workbook_bytes(headers=None), workbook_bytes()],
                         ids=["zero-bytes", "empty-workbook", "headers-only"])
def test_empty_or_headers_only_workbook(contents):
    with pytest.raises(SalesValidationError):
        validate(contents)


INVALID_CELLS = [
    ("shop_id", None, "required"),
    ("shop_id", 101.5, "integer"),
    ("shop_id", "101", "integer"),
    ("shop_id", True, "integer"),
    ("shop_id", 102, "does not match"),
    ("sku_name", "", "required"),
    ("sku_name", " \t\n ", "non-empty"),
    ("sku_name", None, "required"),
    ("sku_name", 123, "non-empty"),
    ("sku_name", "a" * 256, "255"),
    ("sku_name", "=1+1", "formula"),
    ("sku_name", "#N/A", "Excel error"),
    ("num_units_sold", "abc", "numeric"),
    ("num_units_sold", -5, ">= 0"),
    ("num_units_sold", None, "required"),
    ("num_units_sold", True, "numeric"),
    ("num_units_sold", 0.001, "NUMERIC(12,2)"),
    ("num_units_sold", 10000000000, "NUMERIC(12,2)"),
    ("num_units_sold", "=10+10", "formula"),
    ("date", "2026-02-30", "valid Excel date"),
    ("date", None, "required"),
    ("date", 123, "valid Excel date"),
]


@pytest.mark.parametrize("column,value,message", INVALID_CELLS)
def test_invalid_cell_has_row_and_column(column, value, message):
    row = VALID_ROW.copy()
    row[HEADERS.index(column)] = value
    with pytest.raises(SalesValidationError) as error:
        validate(workbook_bytes([row]))
    issue = error.value.errors[0]
    assert issue.row == 2
    assert issue.column == column
    assert message in issue.message


def test_collects_multiple_errors_and_rejects_mixed_shops():
    with pytest.raises(SalesValidationError) as error:
        validate(workbook_bytes([VALID_ROW, [102, " ", -5, "bad date"]]))
    assert {(issue.row, issue.column) for issue in error.value.errors} == {(3, field) for field in HEADERS}
    assert error.value.status_code == 422


@pytest.mark.parametrize("units", [20, 20.5, 0, 0.25, 9999999999.99])
def test_decimal_values_are_preserved(units):
    row = VALID_ROW.copy()
    row[2] = units
    assert validate(workbook_bytes([row]))[0].num_units_sold == Decimal(str(units))


def test_reordered_columns_and_uppercase_extension():
    row = validate(workbook_bytes([list(reversed(VALID_ROW))], list(reversed(HEADERS))), "SALES.XLSX")[0]
    assert row.shop_id == 101
    assert row.sku_name == "Apple"


def test_excel_1904_date_system():
    rows = validate(workbook_bytes([[101, "Apple", 20, date(2026, 10, 1)]], mac_dates=True))
    assert rows[0].date == date(2026, 10, 1)


def test_blank_rows_keep_excel_row_numbers():
    with pytest.raises(SalesValidationError) as error:
        validate(workbook_bytes([VALID_ROW, [None] * 4, [102, "Apple", 1, "2026-10-01"]]))
    assert error.value.errors[0].row == 4


@pytest.mark.parametrize("contents", [b"shop_id,sku_name,num_units_sold,date", b"not an Excel workbook", b"PK\x03\x04"])
def test_renamed_or_corrupt_xlsx_is_rejected(contents):
    with pytest.raises(SalesValidationError) as error:
        validate(contents)
    assert error.value.status_code == 400


def test_extra_worksheets_are_not_silently_ignored():
    with pytest.raises(SalesValidationError, match="validation failed"):
        validate(workbook_bytes([VALID_ROW], second_sheet=True))


def test_macro_workbook_renamed_xlsx_is_rejected():
    contents = rewrite_member(
        workbook_bytes([VALID_ROW]), "[Content_Types].xml",
        lambda value: value.replace(
            b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
            b"application/vnd.ms-excel.sheet.macroEnabled.main+xml",
        ),
    )
    with pytest.raises(SalesValidationError) as error:
        validate(contents)
    assert error.value.status_code == 415


def test_incorrect_dimensions_cannot_hide_another_shop():
    contents = rewrite_member(
        workbook_bytes([VALID_ROW, [102, "Apple", 1, "2026-10-01"]]),
        "xl/worksheets/sheet1.xml", lambda value: value.replace(b'A1:D3', b'A1:D2'),
    )
    with pytest.raises(SalesValidationError) as error:
        validate(contents)
    assert error.value.errors[0].row == 3


def test_data_beyond_header_columns_is_rejected():
    # Simulate a producer that only records four header cells but adds a fifth data cell.
    contents = rewrite_member(
        workbook_bytes([VALID_ROW + ["extra"]]), "xl/worksheets/sheet1.xml",
        lambda value: value.replace(b'A1:E2', b'A1:D2'),
    )
    with pytest.raises(SalesValidationError) as error:
        validate(contents)
    assert error.value.errors[0].row == 2


def test_upload_size_limit():
    with pytest.raises(SalesValidationError) as error:
        validate_sales_upload(workbook_bytes([VALID_ROW]), "sales.xlsx", 101, max_bytes=10)
    assert error.value.status_code == 413


@pytest.mark.parametrize("setting,limit", [("MAX_EXPANDED_BYTES", 10), ("MAX_DATA_ROWS", 1), ("MAX_ARCHIVE_MEMBERS", 1)])
def test_workbook_resource_limits(monkeypatch, setting, limit):
    monkeypatch.setattr(parser, setting, limit)
    with pytest.raises(SalesValidationError) as error:
        validate(workbook_bytes([VALID_ROW, VALID_ROW]))
    assert error.value.status_code == 413


@pytest_asyncio.fixture
async def authenticated(client):
    email = f"upload.{uuid.uuid4().hex}@example.com"
    response = await client.post("/api/v1/auth/register", json={
        "name": "Upload User", "email": email, "password": "UploadPassword!123", "shop_id": 101,
    })
    assert response.status_code == 201
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "UploadPassword!123"})
    assert login.status_code == 200
    return response.json()["id"], {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_authenticated_preview(client, authenticated):
    _, headers = authenticated
    response = await client.post(ENDPOINT, headers=headers, files={
        "file": ("sales.xlsx", workbook_bytes([VALID_ROW, [101, "Banana", 20.5, date(2026, 10, 2)]]), XLSX_MIME),
    })
    assert response.status_code == 200
    assert response.json() == {"success": True, "row_count": 2, "rows": [
        {"shop_id": 101, "sku_name": "Apple", "num_units_sold": "20", "date": "2026-10-01"},
        {"shop_id": 101, "sku_name": "Banana", "num_units_sold": "20.5", "date": "2026-10-02"},
    ]}


@pytest.mark.parametrize("token", [None, "invalid", "expired"])
async def test_missing_invalid_or_expired_auth(client, token):
    if token == "expired":
        token = create_access_token(42, expires_delta=timedelta(seconds=-1))
    response = await client.post(ENDPOINT, headers={"Authorization": f"Bearer {token}"} if token else {},
                                 files={"file": ("sales.xlsx", workbook_bytes([VALID_ROW]), XLSX_MIME)})
    assert response.status_code == 401


@pytest.mark.parametrize("filename,contents,status", [
    ("sales.csv", b"a,b", 415),
    ("sales.xls", b"xls", 415),
    ("sales.json", b"{}", 415),
    ("sales.xlsx", b"not Excel", 400),
    ("sales.xlsx", workbook_bytes(), 422),
    ("sales.xlsx", workbook_bytes([VALID_ROW, [102, " ", -1, "bad"]]), 422),
], ids=["csv", "xls", "json", "corrupt-xlsx", "headers-only", "mixed-shops"])
async def test_http_validation_errors(client, authenticated, filename, contents, status):
    _, headers = authenticated
    response = await client.post(ENDPOINT, headers=headers, files={"file": (filename, contents, XLSX_MIME)})
    assert response.status_code == status
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["errors"]
    assert "rows" not in detail
    if status == 422 and len(detail["errors"]) > 1:
        assert all(issue["row"] == 3 for issue in detail["errors"])


async def test_authorization_uses_database_despite_jwt_query_and_form(client, db_session, authenticated):
    user_id, _ = authenticated
    user = await db_session.get(User, user_id)
    user.shop_id = 102
    await db_session.commit()
    db_session.expunge_all()
    token = create_access_token(user_id, extra_claims={"shop_id": 101})
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post(ENDPOINT + "?shop_id=101", headers=headers, data={"shop_id": "101"},
                                 files={"file": ("sales.xlsx", workbook_bytes([VALID_ROW]), XLSX_MIME)})
    assert response.status_code == 422
    assert "authenticated user's shop_id 102" in response.json()["detail"]["errors"][0]["message"]
    response = await client.post(ENDPOINT, headers=headers, files={
        "file": ("sales.xlsx", workbook_bytes([[102, "Apple", 1, "2026-10-01"]]), XLSX_MIME),
    })
    assert response.status_code == 200


@pytest.mark.parametrize("valid", [True, False])
async def test_validation_never_writes_sales(client, db_session, authenticated, valid):
    # Preserve an existing row too, so DELETE/UPDATE cannot pass a count-only assertion.
    db_session.add(Sale(shop_id=101, sku_name="Existing", num_units_sold=Decimal("7.25"), date=date(2026, 1, 1)))
    await db_session.commit()
    before = (await db_session.execute(select(Sale.__table__).order_by(Sale.id))).all()
    connection = (await db_session.connection()).sync_connection
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    _, headers = authenticated
    event.listen(connection, "before_cursor_execute", capture)
    try:
        rows = [VALID_ROW] if valid else [VALID_ROW, [102, "Apple", 1, "2026-10-01"]]
        response = await client.post(ENDPOINT, headers=headers, files={"file": ("sales.xlsx", workbook_bytes(rows), XLSX_MIME)})
        assert response.status_code == (200 if valid else 422)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert statements and all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
    assert (await db_session.execute(select(Sale.__table__).order_by(Sale.id))).all() == before


async def test_http_size_limit(client, authenticated, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    response = await client.post(ENDPOINT, headers=authenticated[1], files={"file": ("sales.xlsx", b"x" * (1024 * 1024 + 1), XLSX_MIME)})
    assert response.status_code == 413


@pytest.mark.parametrize("member,root_tag", [
    ("[Content_Types].xml", b"Types"),
    ("xl/worksheets/sheet1.xml", b"worksheet"),
])
def test_xml_entity_declarations_are_rejected(member, root_tag):
    contents = rewrite_member(
        workbook_bytes([VALID_ROW]), member,
        lambda value: value.replace(
            b"<" + root_tag,
            b'<!DOCTYPE ' + root_tag + b' [<!ENTITY test "example">]><' + root_tag,
            1,
        ),
    )
    with pytest.raises(SalesValidationError) as error:
        validate(contents)
    assert error.value.status_code == 400
