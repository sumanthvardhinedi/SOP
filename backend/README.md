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

### Phase 1 (Active)
- `GET /health` — Health check endpoint (`{"status": "ok"}`)

### Planned Endpoints (Phases 2–4)
- `POST /api/v1/auth/register` — Register user assigned to a shop
- `POST /api/v1/auth/login` — Authenticate and receive JWT access token
- `GET  /api/v1/auth/me` — Retrieve authenticated user profile and shop context
- `POST /api/v1/uploads/sales` — Upload CSV/Excel sales dataset for `current_user.shop_id`
- `GET  /api/v1/datasets` — List datasets belonging to `current_user.shop_id`
- `GET  /api/v1/sales` — Query historical sales belonging to `current_user.shop_id`

---

## 11. Testing Instructions

Run the test suite using `pytest`:

```bash
pytest -v
```

---

## 12. Future ML Architecture (Phase 5)

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
