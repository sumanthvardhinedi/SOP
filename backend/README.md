# Multi-User, Multi-Shop Sales Data Backend

Existing FastAPI backend using Python **3.14.3**, PostgreSQL **15+**, async
SQLAlchemy, Alembic, Pydantic v2, Argon2id, and PyJWT. This phase provides
**authentication, the simplified sales schema, and Phase 3A Excel upload validation**.
Uploads return a preview only; they never write sales data.

## Database schema

Only two application tables exist. `alembic_version` is migration metadata.

| Table | Columns |
| --- | --- |
| `users` | `id`, `name`, `email`, `password_hash`, `shop_id`, `created_at`, `updated_at` |
| `sales` | `id`, `date`, `shop_id`, `sku_name`, `num_units_sold` |

- `users.email` has a unique index. Timestamps are timezone-aware.
- Both `shop_id` fields are non-null integers, with no foreign keys or shop table.
- `sales.date` is a non-null PostgreSQL `DATE`.
- `sku_name` is a non-null `VARCHAR(255)` with a check rejecting empty/space-only values.
- `num_units_sold` is a non-null, non-negative `NUMERIC(12, 2)`. This retains the
  previous quantity precision, including fractional sales, without rounding or data loss.
- Sales indexes cover `shop_id`, `date`, `sku_name`, and `(shop_id, date)`.
- No dataset, uploader, filename, hash, upload status, or sales timestamp columns exist.

## Setup

From `backend/`, create a Python 3.14.3 virtual environment and install the existing dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On Linux/macOS, activate with `source .venv/bin/activate`.
Create a PostgreSQL development database using your local database administrator:

```sql
CREATE DATABASE sales_db;
```

Configure `DATABASE_URL` (the `postgresql+asyncpg://` driver), `JWT_SECRET_KEY`,
`JWT_ALGORITHM`, and `ACCESS_TOKEN_EXPIRE_MINUTES` through the existing `.env`
or process environment. Keep existing JWT settings to preserve token behavior.
For a new installation, `.env.example` documents the settings; choose a random
JWT secret of at least 32 characters. Never commit secrets or `.env`.

## Migrations

The original checkout shipped Phase 1 models but **no committed revisions**.
Two revisions now provide a reproducible migration history:

1. `0001_phase1_baseline` records the original schema.
2. `0002_simplify_sales` migrates it to `users` and `sales`.

### New, empty database

```powershell
alembic upgrade head
```

### Existing Phase 1 development database

Back up the database before upgrading. Stop application writes during migration.
Compare the existing schema with `alembic/versions/0001_phase1_baseline.py`, including
column types, constraints, and index names. For matching Phase 1 tables with no
Alembic revision recorded, mark the existing schema as the baseline, then upgrade:

```powershell
alembic stamp 0001_phase1_baseline
alembic upgrade head
```

Stamping records a version; it does not create or validate tables. Do not stamp a
partially created or different schema. A database already at the baseline only
needs `alembic upgrade head`.

If the database carries an uncommitted/local revision unknown to this checkout,
retain that migration and a database backup, and verify that its resulting schema
matches the baseline. **Only after that verification**, reconcile its version with
`alembic stamp --purge 0001_phase1_baseline`, then upgrade. If it differs, reconcile
those differences explicitly before stamping. Never use `create_all`, delete users,
or recreate a populated database as an upgrade shortcut.

### Data preservation and removed metadata

The simplification migration removes foreign keys from surviving users/sales before
dropping parent tables. It renames `product` to `sku_name` and `quantity` to
`num_units_sold` in place. Existing user IDs, names, emails, password hashes, shop
IDs, timestamps, and sales IDs/dates/shop IDs/values are preserved. User and sales
sequences continue to work.

Shop records, dataset records, their indexes/status enum, `sales.dataset_id`, and
sales timestamps are permanently removed. This is intentional metadata loss.
The new checks retain the old business constraints, so valid Phase 1 sales need
no cleanup or conversion. Unexpected dependencies/schema differences cause the
PostgreSQL transactional migration to fail and roll back; it does not use `CASCADE`
or silently discard conflicting rows.

Downgrade from `0002_simplify_sales` is deliberately refused: shop names and file
metadata cannot be reconstructed honestly. Restore the pre-upgrade backup if those
records are needed.

Verify the resulting schema:

```powershell
alembic current
alembic check
psql -d sales_db -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
```

Expected tables: `alembic_version`, `sales`, `users`.

## Authentication and shop identity

| Endpoint | Behavior |
| --- | --- |
| `GET /health` | Returns `{"status": "ok"}` |
| `POST /api/v1/auth/register` | Registers a user with a positive integer `shop_id`; no shop record is required |
| `POST /api/v1/auth/login` | Verifies email/password and returns a Bearer JWT |
| `GET /api/v1/auth/me` | Loads the user from PostgreSQL and returns their profile and stored shop ID |
| `POST /api/v1/sales/upload/validate` | Authenticated `.xlsx` validation and preview, with no database writes |

Registration accepts the initial shop assignment as it did in Phase 2, now without
a shop existence lookup. It does not verify ownership of that identifier. Protected
requests authenticate via JWT `sub` (user ID) and derive shop identity from the
stored user, never from a request's shop ID or a token's optional shop claim.
Changes to the stored assignment take effect on subsequent authenticated requests.
Deleted users cannot authenticate using an otherwise valid token.

Passwords use salted Argon2id hashes. API response schemas exclude both passwords
and hashes. PyJWT continues using `JWT_SECRET_KEY`, `JWT_ALGORITHM`, and
`ACCESS_TOKEN_EXPIRE_MINUTES`. Missing, invalid, expired, or unknown-user tokens
return HTTP 401. Duplicate email registration returns HTTP 409.

### PowerShell example

Start the application:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI: `http://127.0.0.1:8000/docs`.
No shop seed is needed:

```powershell
$registerBody = @{
    name = "John"
    email = "john@example.com"
    password = "example-password-change-me"
    shop_id = 101
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/auth/register" `
    -ContentType "application/json" -Body $registerBody

$loginBody = @{
    email = "john@example.com"
    password = "example-password-change-me"
} | ConvertTo-Json
$loginResponse = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/auth/login" `
    -ContentType "application/json" -Body $loginBody

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/auth/me" `
    -Headers @{ Authorization = "Bearer $($loginResponse.access_token)" }
```

## Verification

Run against the migrated development PostgreSQL database from `backend/`:

```powershell
python -m compileall -q app alembic tests
pytest -v
```

Authentication/schema tests use transaction/savepoint rollbacks. Migration tests
create temporary schemas inside rolled-back transactions and exercise empty database
upgrades, populated Phase 1 upgrades, baseline stamping, authentication after
migration, schema/ORM agreement, and refusal of a destructive downgrade. The test
database role needs permission to create schemas. Tests preserve application rows;
PostgreSQL sequences can advance during tests.

## Phase 3A: Excel sales validation

`POST /api/v1/sales/upload/validate` accepts one multipart field named `file` and
requires the existing `Authorization: Bearer <token>` header. Only genuine `.xlsx`
workbooks are supported. CSV, legacy `.xls`, macro-enabled files, other extensions,
and non-Excel content renamed to `.xlsx` are rejected. The supplied MIME header is
not trusted as proof of file format.

The workbook must have exactly one worksheet. Its first row must contain exactly
`shop_id`, `sku_name`, `num_units_sold`, and `date`, once each, in any order. Headers
are case-sensitive; extra columns (including unnamed columns with data) are rejected.
Entirely blank rows are skipped while retaining original Excel row numbers in errors.
An empty workbook or headers without data is rejected. Formulas and Excel error
cells are rejected rather than evaluated or accepted from cached results.

Every data row must satisfy:

- `shop_id`: a numeric integer equal to the authenticated user's current stored
  `shop_id`. Boolean values and numeric strings are not integers for this contract.
- `sku_name`: a non-empty string, not whitespace-only, at most 255 characters.
- `num_units_sold`: a finite numeric value >= 0, fitting the existing `NUMERIC(12,2)`
  column (at most 9999999999.99 and two fractional digits). Numeric strings and
  booleans are rejected. Decimal values are preserved using Python `Decimal`;
  excess precision is rejected, never silently rounded.
- `date`: a native Excel date/datetime cell or an ISO date string such as
  `2026-10-01`, normalized to Python `date`. Excel's 1900 and 1904 date systems
  are handled by openpyxl. Bare numbers without Excel date formatting are rejected.

The endpoint passes only `current_user.shop_id` from `get_current_user` to the
validation service. Query/form shop IDs and optional JWT shop claims cannot override
that value. If even one row is invalid or belongs to another shop, the entire file
is rejected without a partial success preview.

### Responses

Valid files return HTTP 200. Pydantic serializes Decimal quantities as JSON strings
to preserve exact decimal values; dates use ISO strings:

```json
{
  "success": true,
  "row_count": 1,
  "rows": [
    {"shop_id": 101, "sku_name": "Apple", "num_units_sold": "20.5", "date": "2026-10-01"}
  ]
}
```

Invalid rows return HTTP 422 with all detected row/field issues:

```json
{
  "detail": {
    "success": false,
    "errors": [
      {"row": 3, "column": "shop_id", "message": "shop_id 102 does not match authenticated user's shop_id 101"},
      {"row": 3, "column": "num_units_sold", "message": "num_units_sold must be >= 0"}
    ]
  }
}
```

File-level errors use `null` for row/column when unavailable. Unsupported formats
return 415, unreadable/corrupt workbooks 400, oversized files/workbooks 413, and
missing/invalid/expired authentication 401. The existing `MAX_UPLOAD_SIZE_MB`
setting limits the compressed file (20 MiB by default). Parsing also limits total
uncompressed ZIP members to 100 MiB, archive entries to 1,000, and worksheet data
rows (including blanks) to 50,000 to bound preview processing.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sales/upload/validate \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sales.xlsx"
```

`app/uploads/router.py` handles authentication/HTTP and runs the synchronous
validation service in a worker thread. `service.py` accepts bytes, filename, and
trusted shop ID; `parser.py` reads using openpyxl; `schemas.py` defines the preview
and structured errors. The parser/service receive no database session and contain
no INSERT, UPDATE, DELETE, synchronization, or upsert operations. Authentication,
models, and migrations are unchanged. Phase 3B and ML are not implemented.

Dependencies added through `requirements.txt`: `openpyxl`, `python-multipart`
(the FastAPI multipart upload dependency), and `defusedxml` (blocks XML entity
expansion in untrusted workbooks). Tests generate all workbooks in memory
and cover file/column/row validation, decimals/dates, JWT authorization, size limits,
and unchanged existing sales plus absence of write SQL for valid and invalid files.
