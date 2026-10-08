# Multi-User, Multi-Shop Sales Data Backend

A modular, extensible Python **3.14.3** backend built with **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.x (Async)**, **Alembic**, and **Pydantic v2** for managing multi-shop historical sales datasets with strict shop-level data isolation.

---

## 1. Architecture Overview

- **Multi-Shop Tenant Isolation**: Each user is bound to a `Shop` (`users.shop_id -> shops.id`). The backend resolves the active shop exclusively from the authenticated user's database record (`current_user.shop_id`)—never from client-supplied query parameters or request bodies.
- **Extensible File Ingestion Layer**: External CSV/Excel formats (`Date | Product | Quantity` today, or arbitrary column names in the future) are normalized by `app/uploads/parser.py` into a canonical internal schema before reaching the database.
- **Dataset Lineage & Deduplication**: Every file upload creates a `Dataset` record storing a SHA-256 `file_hash`, row count, status (`UPLOADED`, `PROCESSING`, `COMPLETED`, `FAILED`), and date range (`date_from`, `date_to`).
- **ML-Ready Separation**: The `sales` table stores verified historical sales only. Future forecasting models live strictly under `app/ml/` without coupling to authentication, upload, or core transactional tables.

```text
Shop
 ├── Users (users.shop_id)
 ├── Datasets (datasets.shop_id, datasets.uploaded_by)
 │    └── Sales (sales.dataset_id)
 └── Sales (sales.shop_id)
```

---

## 2. Technology Stack

- **Runtime**: Python `3.14.3`
- **Web Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy `2.x` (`AsyncSession` + `asyncpg`)
- **Migrations**: Alembic (configured for async SQLAlchemy)
- **Settings & Validation**: Pydantic v2 + `pydantic-settings`
- **Authentication (Phase 2)**: `PyJWT` + `argon2-cffi`
- **File Processing (Phase 3)**: `pandas`, `openpyxl`, `python-multipart`

---

## 3. Prerequisites

- **Python 3.14.3** (`python --version` should report `Python 3.14.3`)
- **PostgreSQL 15+** running locally or accessible via network

---

## 4. Virtual Environment Setup (Windows & Python 3.14.3)

Navigate to the `backend/` directory and create the virtual environment:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment on Windows:

```bash
.venv\Scripts\activate
```

Verify the active Python version inside the virtual environment:

```bash
python --version
# Expected output: Python 3.14.3
```

---

## 5. Dependency Installation

Upgrade `pip` and install the dependencies from `requirements.txt`:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 6. PostgreSQL Setup

Open `psql` (or pgAdmin) and create the `sales_db` database:

```sql
CREATE DATABASE sales_db;
```

Or via the command line:

```bash
psql -U postgres -c "CREATE DATABASE sales_db;"
```

---

## 7. Environment Variables (`.env` Setup)

Copy `.env.example` to `.env` inside the `backend/` folder:

```bash
copy .env.example .env
```

Update `.env` with your local PostgreSQL credentials and a strong JWT secret:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/sales_db

JWT_SECRET_KEY=replace-with-a-secure-random-secret-key-at-least-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

MAX_UPLOAD_SIZE_MB=20
```

> **Security Note**: `.env` is listed in `.gitignore` and must never be committed to version control.

---

## 8. Alembic Database Migrations

Generate the initial schema migration from the SQLAlchemy 2.x models (`Shop`, `User`, `Dataset`, `Sale`):

```bash
alembic revision --autogenerate -m "initial schema"
```

Apply the migration to PostgreSQL:

```bash
alembic upgrade head
```

---

## 9. Running FastAPI

Start the development server from the `backend/` directory:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Interactive Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc Documentation**: `http://127.0.0.1:8000/redoc`

---

## 10. API Endpoints

### Active Endpoints (Phase 1 & Phase 2)
- `GET  /health` — Health check endpoint (`{"status": "ok"}`)
- `POST /api/v1/auth/register` — Register a new user assigned to an existing shop
- `POST /api/v1/auth/login` — Authenticate with email and password to receive a Bearer JWT access token
- `GET  /api/v1/auth/me` — Retrieve the authenticated user's profile and authoritative `shop_id`

### Planned Endpoints (Phases 3–4)
- `POST /api/v1/uploads/sales` — Upload CSV/Excel sales dataset for `current_user.shop_id`
- `GET  /api/v1/datasets` — List datasets belonging to `current_user.shop_id`
- `GET  /api/v1/sales` — Query historical sales belonging to `current_user.shop_id`

---

## 11. Phase 2 Authentication & Multi-Shop Isolation

### How Authentication Works
1. **Password Security (`app/core/security.py`)**:
   - Plaintext passwords are hashed using **Argon2id** (`argon2-cffi`) before reaching PostgreSQL.
   - Plaintext passwords are never stored, logged, or placed in JWT tokens.
   - `password_hash` is never exposed in any API response (`UserResponse` schema excludes it).
2. **JWT Access Tokens (`PyJWT`)**:
   - On successful login (`POST /api/v1/auth/login`), the backend issues a signed JWT using `JWT_SECRET_KEY`, `JWT_ALGORITHM` (`HS256`), and `ACCESS_TOKEN_EXPIRE_MINUTES`.
   - Claims include `sub` (stringified `user.id`), `iat` (issued-at timestamp), `exp` (expiration timestamp), and `type` (`"access"`).
3. **Current-User Dependency (`get_current_user` in `app/core/dependencies.py`)**:
   - Extracts the Bearer token from `Authorization: Bearer <access_token>`.
   - Validates signature, token type, and expiration (`exp`).
   - Queries PostgreSQL for the `User` record matching `sub`.
   - Rejects missing, malformed, tampered, expired, or non-existent user tokens with `HTTP 401 Unauthorized`.

### Authoritative Shop Isolation Rule
Each user belongs to a single shop (`users.shop_id -> shops.id`).
- During registration (`POST /api/v1/auth/register`), `shop_id` links the newly created account to an existing shop in `shops`.
- **After login, the client never selects or supplies `shop_id`**.
- Every protected endpoint resolves the user via `current_user: User = Depends(get_current_user)` and uses `current_user.shop_id` directly from PostgreSQL. Any client-supplied `shop_id` in query strings or payloads is ignored for authorization.

---

## 12. PowerShell API Usage & Testing Examples

### Step 1: Seed a Shop in PostgreSQL (if `shops` is empty)
Before registering a user with `shop_id: 1`, ensure at least one shop exists in `sales_db`:

```powershell
psql -U postgres -d sales_db -c "INSERT INTO shops (name) VALUES ('Downtown Flagship Shop'), ('Uptown Branch Shop') ON CONFLICT (name) DO NOTHING; SELECT id, name FROM shops;"
```

### Step 2: Verify `/health` in PowerShell

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health"
```

Expected output:

```text
status
------
ok
```

### Step 3: Register a User (`POST /api/v1/auth/register`)

```powershell
$registerBody = @{
    name     = "John"
    email    = "john@example.com"
    password = "strong-password"
    shop_id  = 1
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:8000/api/v1/auth/register" `
    -ContentType "application/json" `
    -Body $registerBody
```

Expected response (`201 Created`):

```json
{
  "id": 1,
  "name": "John",
  "email": "john@example.com",
  "shop_id": 1
}
```

### Step 4: Log In & Capture the JWT (`POST /api/v1/auth/login`)

```powershell
$loginBody = @{
    email    = "john@example.com"
    password = "strong-password"
} | ConvertTo-Json

$loginResponse = Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:8000/api/v1/auth/login" `
    -ContentType "application/json" `
    -Body $loginBody

$token = $loginResponse.access_token
$loginResponse
```

Expected response (`200 OK`):

```json
{
  "access_token": "<JWT_TOKEN>",
  "token_type": "bearer"
}
```

### Step 5: Call Authenticated `/api/v1/auth/me`

```powershell
Invoke-RestMethod -Method Get `
    -Uri "http://127.0.0.1:8000/api/v1/auth/me" `
    -Headers @{ Authorization = "Bearer $token" }
```

Expected response (`200 OK`):

```json
{
  "id": 1,
  "name": "John",
  "email": "john@example.com",
  "shop_id": 1
}
```

---

## 13. Running the Automated Test Suite

The test suite (`tests/test_auth.py`) runs in-process via `httpx.AsyncClient` and `ASGITransport` (no manually running Uvicorn server required) and uses SQLAlchemy savepoint rollbacks so your `sales_db` database stays completely clean after test execution.

From the `backend/` directory (with `.venv` activated):

```powershell
pytest -v
```

---

## 14. Security Notes on `.env`

- Never commit `.env` to Git (`.env` is ignored via `.gitignore`).
- Never place real PostgreSQL passwords or `JWT_SECRET_KEY` values inside `.env.example`, `README.md`, or source files.
- Keep `JWT_SECRET_KEY` local in `backend/.env` with at least 32 characters of cryptographic randomness.

---

## 15. Future ML Architecture (Phase 5)

Future forecasting models (XGBoost, LightGBM, Random Forest, Prophet) will reside under `app/ml/`:

```text
app/ml/
├── features/     # Feature extraction from historical shop sales
├── training/     # Model training pipelines per shop/product
├── models/       # Serialized model artifacts & wrappers
├── prediction/   # Forecast generation services
└── evaluation/   # Accuracy metrics and backtesting
```

Actual historical sales remain strictly inside the `sales` table; generated forecasts are stored and served separately.
