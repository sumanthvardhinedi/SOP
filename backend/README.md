# Multi-User, Multi-Shop Sales Data Backend

Existing FastAPI backend using Python **3.14.3**, PostgreSQL **15+**, async
SQLAlchemy, Alembic, Pydantic v2, Argon2id, and PyJWT. This phase provides
**authentication, Excel validation (Phase 3A), atomic sales persistence (Phase 3B),
authenticated sales retrieval (Phase 3C), and isolated next-day forecasting**.
The validation endpoint remains read-only; the upload endpoint inserts or replaces daily sales.

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
- A unique constraint enforces one sale per `(shop_id, date, sku_name)`.
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
Three revisions provide a reproducible migration history:

1. `0001_phase1_baseline` records the original schema.
2. `0002_simplify_sales` migrates it to `users` and `sales`.
3. `0003_sales_business_key` adds unique `(shop_id, date, sku_name)` enforcement.

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
| `POST /api/v1/sales/upload` | Authenticated validation and atomic insert/update of daily sales |
| `GET /api/v1/sales` | Retrieve the authenticated shop's sales with optional date/SKU filters |

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
no database operations. The Phase 3B route calls the separate persistence module
after validation. Authentication is unchanged; ML is not implemented.

Dependencies added through `requirements.txt`: `openpyxl`, `python-multipart`
(the FastAPI multipart upload dependency), and `defusedxml` (blocks XML entity
expansion in untrusted workbooks). Tests generate all workbooks in memory
and cover file/column/row validation, decimals/dates, JWT authorization, size limits,
and unchanged existing sales plus absence of write SQL for valid and invalid files.


## Phase 3B: Persist validated sales

`POST /api/v1/sales/upload` accepts the same multipart `file` and Bearer JWT as the
preview endpoint. It reuses the Phase 3A parsing/validation service and additionally
rejects duplicate `(shop_id, date, sku_name)` keys within the workbook. Errors retain
the structured `detail.success`/`detail.errors` format, including the duplicate's
Excel row number and the first matching row. Date normalization happens before
comparison. SKU names are compared exactly; no trimming, case-folding, summing, or
silent choice of a duplicate row occurs. `/validate` retains its Phase 3A behavior,
including previewing duplicate rows without persisting them.

On success, for example:

```json
{"success": true, "row_count": 10, "inserted_count": 7, "updated_count": 3}
```

`app/uploads/persistence.py` uses the existing request-scoped async SQLAlchemy
session and PostgreSQL `INSERT ... ON CONFLICT ON CONSTRAINT
uq_sales_shop_id_date_sku_name DO UPDATE`. A conflict replaces only
`num_units_sold`; it preserves the existing ID and key. Existing 20 plus uploaded 25
results in 25. A repeated upload updates the same records without creating duplicates.
Counts come from PostgreSQL `RETURNING` (`xmax = 0` distinguishes inserted tuples
from conflict updates), rather than a pre-write lookup. An existing record counts
as updated even if its quantity is unchanged.

The route obtains `current_user.shop_id` through the existing JWT/database flow.
The validation service checks every row against that stored assignment, and the
persistence service verifies it again and sets the stored shop ID on each write.
Query/form values and JWT shop claims never authorize another shop. The conflict
key includes shop ID, so another shop's records cannot be updated by this upload.

All rows are validated before any sales writes. Upserts are sent in batches of
1,000 rows to stay under asyncpg's parameter limit, ordered by business key to use a
consistent lock order for competing uploads. Every batch shares one transaction,
including the session transaction opened by authentication. A single commit happens
after all batches succeed. Any write or commit failure rolls back all inserts and
updates from the upload, including completed earlier batches. Database failures
return HTTP 500 with a safe error message; validation errors return their existing
4xx details. Concurrent writes to the same key are serialized by PostgreSQL; a
successful later conflict update replaces the quantity.

### Apply the Phase 3B migration

From `backend/`, using the existing development database settings:

```powershell
alembic upgrade head
alembic check
```

`0003_sales_business_key` adds only the unique constraint and its backing index.
No application table or column is added. It takes an exclusive lock on `sales`
through the duplicate check and constraint creation, blocking other access during
the migration. Schedule accordingly for populated databases.

If duplicate business keys already exist, the migration fails explicitly and rolls
back without deleting or merging business data. Inspect conflicts with:

```sql
SELECT shop_id, date, sku_name, count(*)
FROM sales
GROUP BY shop_id, date, sku_name
HAVING count(*) > 1;
```

Back up the database and decide explicitly which business values are correct before
resolving duplicates and retrying. There is no automatic deduplication policy.
To reverse only Phase 3B, use `alembic downgrade 0002_simplify_sales`; this removes
the unique constraint and preserves every row. Stop using the persistence endpoint
when downgraded, since its upsert requires that constraint. Earlier migrations are
unchanged, including the documented irreversible Phase 1 metadata removal.

### Phase 3B tests

Run `pytest -v` as before. New tests use real PostgreSQL for insert/update counts,
replacement, mixed operations, duplicate rejection, shop isolation, uniqueness,
migration reversal/duplicate refusal, and concurrent upserts. A real database check
failure in a later batch verifies that an earlier insert and update both roll back.
The concurrency test creates and removes its own isolated schema; other persistence
and migration tests use temporary schemas inside rolled-back transactions. Existing
development sales and users do not affect these tests. Phase 3A and authentication regression tests remain
in the full suite. No additional dependencies are needed.


## Phase 3C: Retrieve sales

`GET /api/v1/sales` requires `Authorization: Bearer <token>` and returns only sales
whose `shop_id` matches the authenticated user's current database record. The
existing `get_current_user` dependency verifies JWT identity and loads that record.
Missing, invalid, and expired credentials return HTTP 401.

Optional query parameters:

| Parameter | Meaning |
| --- | --- |
| `start_date` | Inclusive earliest date, such as `2026-01-01` |
| `end_date` | Inclusive latest date, such as `2026-10-08` |
| `sku_name` | Exact name, preserving case and spaces; blank/whitespace-only values are invalid |

Filters can be combined. Invalid dates or `start_date > end_date` return HTTP 422
with validation details. Unsupported query parameters are ignored, consistent with
existing endpoints. In particular, a supplied `shop_id` cannot change the authorized
shop, and optional shop claims in a JWT are not used for ownership.

Example request:

```bash
curl --get http://127.0.0.1:8000/api/v1/sales \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "start_date=2026-01-01" \
  --data-urlencode "end_date=2026-10-08" \
  --data-urlencode "sku_name=ProductA"
```

Example response:

```json
{
  "items": [
    {
      "id": 1,
      "date": "2026-10-01",
      "shop_id": 101,
      "sku_name": "ProductA",
      "num_units_sold": "20.50"
    }
  ],
  "total": 1
}
```

Results are ordered by `date` ascending, then `id` ascending. `total` is the number
of records returned after filtering; there is no pagination in this phase. Empty
results return `{"items": [], "total": 0}`. Decimal quantities are serialized as
strings using the same Pydantic convention as upload previews, preserving the
existing `NUMERIC(12,2)` precision. Each item contains only the five public sales
fields shown above.

`app/sales/router.py` uses the existing JWT and async-session dependencies.
`schemas.py` validates the query and defines the response. `service.py` applies
mandatory shop ownership, optional filters, and ordering in the SQLAlchemy query.
The endpoint performs reads only. Phase 3C requires no migration or new dependency.
The complete test suite includes PostgreSQL retrieval tests in isolated transactional
schemas, plus the existing authentication and Phase 3A/3B regression tests.

## Authenticated next-day forecasting

`POST /api/v1/predictions` trains the supplied pandas/sklearn `LinearRegression`
baseline on the authenticated shop's stored sales and returns next-day forecasts.
Install the updated `requirements.txt` (adds pandas and scikit-learn; Python 3.14
wheels supported). No migration, environment variable, or schema change is needed.

```sh
curl -X POST "$API_BASE_URL/api/v1/predictions" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

No request body or query filter is required. Unknown body/query values are ignored
and cannot choose a shop. Ownership comes exclusively from the database user
loaded by the existing JWT dependency. Missing, invalid, or expired tokens return
401. Existing authentication, Excel endpoints, and sales GET behavior are unchanged.

Example response shape (illustrative values, not a prediction accuracy claim):

```json
{
  "status": "ok",
  "forecast_date": "2026-10-09",
  "items": [{"sku_name": "Apple", "predicted_units": 21}],
  "total": 1,
  "training_rows": 14,
  "skipped": [],
  "warnings": []
}
```

- One pooled estimator is fitted per request using only that shop's complete
  historical windows. SKU names map to the supplied model's `sku_id` input.
- Features: 7/14/21/28-day lags and shifted rolling means, weekend, and the supplied
  Indian festival list. Means never cross SKU boundaries or include target sales.
- Forecast date: **the day after the shop's latest stored sales date**. It may be
  in the past if stored history is old; it is not automatically tomorrow.
- Missing dates are **not zero-filled**. Training needs at least one 29-day
  consecutive SKU history. Prediction needs the 28 consecutive days ending at
  the shop's latest date. Other SKUs can contribute training within the same shop.
- `skipped` entries contain `sku_name`, `reason` (`incomplete_history` or
  `insufficient_training_data`), and a readable `message`. No eligible predictions
  returns `status: "insufficient_history"`, `items: []`, `total: 0`; an empty shop
  returns `status: "no_sales"`, `forecast_date: null`, and empty lists.
- Predictions are non-negative whole units, rounded to nearest even at exact
  halves. Decimal historical data is never altered. There are **no database writes**.
- Festival features cover only the supplied 2026 calendar. A `warnings` entry
  explicitly reports when dates outside that year use festival flag zero.
- Unusable stored dates/quantities return a clear 422. Unexpected computation
  failures use the existing sanitized 500 handler. Insufficient data is not a 500.

Training and inference run in a worker thread, using detached values from the
existing async SQLAlchemy session. No model files, prediction tables, frontend
changes, or new database/auth infrastructure are introduced. This is a baseline;
forecast accuracy has not been backtested. See [model notes](app/ml/README.md).

Forecast tests in `tests/test_forecasting_model.py` and
`tests/test_forecasting_api.py` cover causal/grouped features, missing daily
history, real estimator predictions, rounding, festival dates, shop isolation,
JWT handling, worker execution, and SQL read-only behavior. Run the complete
backend suite with `pytest -v` using the existing PostgreSQL test setup.
