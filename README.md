# UshuruLens — KRA Reconciliation API

> KRA Reconciliation & Tax Compliance Engine — powered by Techbiz Group.

**UshuruLens** is a full-stack tax reconciliation platform that matches **SAP Business One** invoice data against **KRA iTax** CSV exports. It detects matched, mismatched, and missing invoices, highlights discrepancies field-by-field, and exports the results for audit and compliance.

## Features

- **SAP Business One Service Layer integration** — async `httpx` client, session (cookie) management, and OData `Prefer`-header pagination for pulling sales (A/R) and purchase (A/P) invoices by date range.
- **KRA iTax CSV ingestion** — validates headers, data types, and duplicates; configurable parsing profiles with field aliases; downloadable CSV templates.
- **Reconciliation engine** — O(n) CU-number-based matching with a fallback pairing heuristic for CU typos. Classifies every document into ten canonical statuses (`Match`, `Missing in SAP/KRA`, `Missing CU Number`, `Amount/VAT/CU/PIN Mismatch`, `Multiple Mismatches`, `Duplicate Source Key`) with `Decimal`-safe comparisons and field-level discrepancy remarks.
- **Multi-company support** — per-company SAP connections, settings, base-amount policies, VAT mappings, and CU source configuration.
- **Background SAP loading** — long-running invoice loads with status tracking and polling endpoints.
- **Reporting & export** — styled Excel (XLSX) workbooks and ZIP archive exports via pluggable export strategies.
- **Authentication** — JWT access tokens (30 min) + rotating, SHA-256-hashed refresh tokens (7 days) stored in the database, with logout revocation and password reset via SendGrid SMTP.
- **Role-based user management** — admin/checker roles, own-profile read-only mode.
- **Web dashboard** — Next.js frontend with sales, purchases, and settings workspaces.
- **Containerized deployment** — single multi-stage Docker image serving the Next.js static export through Nginx and proxying `/api` to FastAPI.

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn, Pydantic (v2) / Pydantic-Settings |
| ORM / DB | SQLAlchemy 2.0, Alembic, PostgreSQL 16 (SQLite fallback for local dev) |
| SAP client | `httpx` AsyncClient + SAP B1 Service Layer |
| Auth | `python-jose` (JWT HS256), `passlib[bcrypt]`, opaque refresh tokens |
| Data / exports | Pandas, OpenPyXL, ZIP |
| Frontend | Next.js 16, React 19, Tailwind CSS 4, TypeScript |
| Infra | Docker, docker-compose, Nginx, GitHub Actions |

## Repository Layout

```
app/
  api/v1/            # FastAPI routers: auth, sales, purchases, reconciliation,
                     # sessions, templates, settings, users, company, import_profiles
  core/              # config (settings), security, exceptions, sap_client, csv_aliases
  database/          # engine, session, ORM base
  domain/            # enums & constants (reconciliation status, invoice type, etc.)
  models/            # SQLAlchemy ORM models
  repositories/      # persistence queries & projections
  reporting/         # Excel/ZIP export strategies, workbook & artifact builders
  schemas/           # Pydantic request/response schemas
  services/          # auth, reconciliation, kra, sap_mapper, invoice, settings, ...
frontend/
  src/app/           # Next.js app router pages (login, dashboard: sales/purchases/settings)
  src/features/      # feature components, hooks, workspace state, API clients
alembic/             # database migrations
docs/                # architecture, reconciliation, SAP integration, auth docs
tests/               # pytest suite
deploy/              # docker-compose files
```

## Getting Started

### Prerequisites

- Python 3.14+ and [uv](https://docs.astral.sh/uv/) (or pip)
- Node.js 20+ and npm
- PostgreSQL 16 (optional for local dev; SQLite is the default fallback)

### Backend (API)

```bash
cp .env.example .env        # adjust values as needed
uv sync                     # install dependencies
uv run uvicorn app.main:app --reload
```

The API is now available at <http://localhost:8000>, interactive docs at <http://localhost:8000/docs>, and the health check at <http://localhost:8000/health>.

### Frontend (dashboard)

```bash
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL` (e.g. `http://localhost:8000/api/v1`) for the frontend to reach the API.

### Database migrations

```bash
uv run alembic upgrade head
uv run python -m app.init_db   # creates schema and seeds admin accounts
```

## Configuration

All configuration is read from the environment (see `.env.example` for the full list). Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/kra_reconciliation.db` | SQLAlchemy connection string |
| `SECRET_KEY` | (dev default) | JWT signing secret — **change in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | `30` / `7` | Token lifetimes |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed frontend origins |
| `SAP_BASE_URL` | — | SAP B1 Service Layer root (e.g. `https://host:50000/b1s/v1`) |
| `SAP_USERNAME` / `SAP_PASSWORD` / `SAP_COMPANY_DB` | — | Service Layer credentials |
| `SAP_PAGE_SIZE` | `1000` | Page size for paginated SAP queries |
| `SAP_BASE_AMOUNT_POLICY` | `skip` | Per-company policy override (`skip`/`reject`/`allow`) |
| `AMOUNT_TOLERANCE` | `10.00` | Allowed amount difference when comparing |
| `MAX_UPLOAD_SIZE_MB` | `5` | Max KRA CSV upload size |
| `MAIL_*` | SendGrid SMTP | Email delivery for password reset |

## Docker Deployment

Build and run the full stack (PostgreSQL + API + frontend behind Nginx):

```bash
cp .env.example .env
docker compose -f deploy/docker-compose.yml up --build
```

The container starts Nginx on port `8000`, which serves the built frontend and proxies `/api` to the FastAPI backend on `127.0.0.1:8001`. Database migrations and admin seeding run automatically at startup via `docker-entrypoint.sh`.

## API Overview

All endpoints are versioned under `/api/v1`.

| Area | Endpoints (examples) |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/token`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` |
| Sales / Purchases | `GET /sales/load`, `POST /sales/import-kra`, `POST /sales/compare` (same for `/purchases/*`) |
| Sessions | Session lifecycle + background SAP load status & polling |
| Reconciliation | Results retrieval, summaries, side-by-side tax bases |
| Templates | KRA CSV template download |
| Settings | Company profile, SAP connections, VAT mappings, KRA parsing profiles, system settings, import profiles |
| Users / Company | User management and company records |

Open <http://localhost:8000/docs> for the complete, interactive OpenAPI spec.

## How Reconciliation Works

1. **Load** — the API pulls invoices from SAP Business One (Service Layer) for a date range and creates a session.
2. **Import** — the user uploads a KRA iTax CSV; headers, types, and duplicates are validated.
3. **Compare** — an O(n) engine groups both datasets by CU number, pairs documents (with a fallback heuristic for minor CU typos), and evaluates amount, VAT breakdown, CU number, and KRA PIN. Each pair is classified into one of ten statuses and produces field-level remarks, e.g. `Base Amount differs (SAP: 1200.00, KRA: 1250.00)`.
4. **Export** — matched/mismatched results are exported as styled Excel or ZIP archives.

## Documentation

- [System Architecture & Testing](docs/system_architecture_testing.md)
- [Reconciliation Engine](docs/reconciliation_engine.md)
- [SAP Business One Integration](docs/sap_integration.md)
- [Authentication Module](docs/auth_docs.md)
- [KRA CSV Parsing & Sessions](docs/session_store_kra_csv.md)

## Testing

```bash
uv run python -m pytest tests/
```

The test suite runs against an ephemeral SQLite database and covers auth, sales/purchases, reconciliation, SAP integration, imports, exports, settings, templates, and VAT normalization.

## License

Proprietary — © Techbiz Group. All rights reserved.
