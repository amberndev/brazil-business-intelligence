# Brazil Business Intelligence

API + dashboard exposing Brazilian public company data (Receita Federal, PGFN, CGU)
for international due-diligence, market-entry, and compliance use cases.

- **backend/** — FastAPI (Python 3.12, asyncpg, no ORM), port **8100**
- **frontend/** — Next.js 14 App Router (TypeScript, Tailwind, shadcn/ui), port **3100**
- **Domain:** brazil.ambern.dev

> **The interface both sides MUST obey is defined in [CONTRACT.md](./CONTRACT.md).**

---

## Run locally

### Prerequisites

- Docker + Docker Compose (for local Postgres)
- Python 3.11+ (3.12 recommended)
- Node.js 22

### Backend

```bash
# 1. Start local Postgres (port 5433)
docker compose -f backend/docker-compose.dev.yml up -d

# 2. Create and activate venv
cd backend
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install deps
pip install -r requirements.txt

# 4. Copy env and fill in values
cp .env.example .env
# Edit .env — DATABASE_URL points at the local Postgres from step 1:
# DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME

# 5. Seed schema + fake data
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME \
    python scripts/seed.py

# 6. Start API
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```

API available at http://localhost:8100

```bash
# Health (no auth required)
curl http://localhost:8100/v1/health

# Company lookup (replace with a dev key from scripts/seed.py output)
curl -H "X-API-Key: bbi_dev_free_key_0000000000000000" \
     http://localhost:8100/v1/company/11222333000181

# Search
curl -H "X-API-Key: bbi_dev_free_key_0000000000000000" \
     "http://localhost:8100/v1/search?q=demo&limit=5"

# Create a FREE key (no auth)
curl -X POST http://localhost:8100/v1/keys \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","name":"Test"}'
```

### Frontend

```bash
cd frontend

# 1. Install deps
npm install

# 2. Copy env
cp .env.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8100  (default; points at local backend)

# 3. Start dev server
npm run dev
```

App available at http://localhost:3100

---

## Deploy to VPS

### Prerequisites (local machine)

- `ssh worbita-dados` alias configured in `~/.ssh/config` (or set `BBI_SSH_ALIAS`)
- `rsync` available locally
- `CONTACT_EMAIL` env var set

### Steps

```bash
export BBI_SSH_ALIAS=worbita-dados   # default; can be omitted
export CONTACT_EMAIL=ops@ambern.dev

bash deploy/deploy.sh
```

The script is **idempotent** — safe to re-run on subsequent deploys.

### What deploy.sh does (in order)

1. `rsync` repo to `/opt/brazil-business-intelligence` on the VPS
2. Creates `backend/.venv` (Python 3.12) and installs `requirements.txt`
3. `npm ci` + `next build` in `frontend/`
4. `apt-get install -y redis-server`, binds to `127.0.0.1:6379`
5. Derives `DATABASE_URL` on-server from `RECEITA_DATABASE_URL` in `/opt/worbita/app/.env` — **never logged or echoed**
6. Writes `/opt/brazil-business-intelligence/.env` (chmod 600)
7. Applies `backend/migrations/001_product_schema.sql` (idempotent DDL, no seed)
8. Installs and starts `bbi-api.service` and `bbi-web.service` via systemd
9. DNS guard: if `brazil.ambern.dev` resolves to the VPS IP → installs Caddy snippet and reloads; otherwise stages the snippet and prints an escalation notice
10. Localhost smoke checks on `:8100/v1/health` and `:3100`

### Deploy artifacts (in `deploy/`)

| File | Purpose |
|---|---|
| `bbi-api.service` | systemd unit for uvicorn (backend, 127.0.0.1:8100) |
| `bbi-web.service` | systemd unit for Next.js start (frontend, 127.0.0.1:3100) |
| `Caddyfile.brazil.snippet` | Caddy reverse-proxy block for brazil.ambern.dev |
| `deploy.sh` | Idempotent deploy script — see above |

---

## Environment variables

### Backend (`backend/.env.example`)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection (receita data + product schema) |
| `REDIS_URL` | Redis URL for rate-limit cache (optional — in-memory fallback if absent) |
| `CONTACT_EMAIL` | From/contact address for email hook stubs |
| `API_ENV` | `development` \| `production` |
| `CORS_ORIGINS` | Comma-separated allowed origins |

### Frontend (`frontend/.env.example`)

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL (default `http://localhost:8100`; prod = `https://brazil.ambern.dev/api`) |
| `NEXT_PUBLIC_SITE_URL` | Canonical site URL for Next.js metadata |
| `CONTACT_EMAIL` | Contact address for PRO/Enterprise CTA stubs |

---

## Pending credentials / actions before first prod deploy

1. **DATABASE_URL on VPS** — `RECEITA_DATABASE_URL` must be present in `/opt/worbita/app/.env`. The deploy script derives `DATABASE_URL` from it on-server.
2. **DDL permissions** — The role in `DATABASE_URL` must have `CREATE SCHEMA` + `CREATE TABLE` privileges on the worbita database to apply `001_product_schema.sql`. If `prospecta_readonly` lacks these, have a DBA apply the migration manually before the first deploy.
3. **SSH alias** — ensure `worbita-dados` resolves in `~/.ssh/config` (or override with `BBI_SSH_ALIAS`).
4. **CONTACT_EMAIL** — set before running `deploy.sh`.
5. **PRO/ENTERPRISE keys** — after launch, insert rows into `product.api_keys` for paid customers (the schema is applied by the deploy).
6. **Email hooks** — `CONTACT_EMAIL` stubs in backend and frontend are no-ops; wire SMTP when ready.

---

## Architecture

```
Browser → https://brazil.ambern.dev/api/v1/... 
       → Caddy (handle_path /api/* strips /api)
       → FastAPI uvicorn 127.0.0.1:8100
       → PostgreSQL (worbita DB, receita + product schema)

Browser → https://brazil.ambern.dev/...
       → Caddy (all other paths)
       → Next.js 127.0.0.1:3100
```

See [CONTRACT.md](./CONTRACT.md) for the full API contract, plans, TypeScript types, and declared stubs.

---

## Complete route index

All routes the backend exposes, in one place. Local base: `http://localhost:8100`.
Prod base (via Caddy `/api` strip): `https://brazil.ambern.dev/api`.

| Method | Path | Auth required | Min plan | Category |
|---|---|---|---|---|
| `GET` | `/v1/health` | None | Public | Contract #1 |
| `GET` | `/v1/company/{cnpj}` | `X-API-Key` | FREE | Contract #2 |
| `GET` | `/v1/company/{cnpj}/compliance` | `X-API-Key` | STARTER | Contract #3 |
| `GET` | `/v1/company/{cnpj}/shareholders` | `X-API-Key` | STARTER | Contract #4 |
| `POST` | `/v1/company/batch` | `X-API-Key` | STARTER | Contract #5 (body: `{"cnpjs":[...]}`) |
| `GET` | `/v1/search` | `X-API-Key` | FREE (JSON) / PRO (CSV) | Contract #6 |
| `GET` | `/v1/market/overview` | `X-API-Key` | PRO | Contract #7 |
| `POST` | `/v1/keys` | None | Public (self-serve) | Key management |
| `GET` | `/v1/keys/me` | `X-API-Key` | Any active key | Key management |
| `DELETE` | `/v1/keys/me` | `X-API-Key` | Any active key | Key management |
| `GET` | `/openapi.json` | None | Public | FastAPI built-in |
| `GET` | `/docs` | None | Public | FastAPI Swagger UI |
| `GET` | `/redoc` | None | Public | FastAPI ReDoc |

**Prod curl examples** (all `/api/v1/...` — Caddy strips `/api` before forwarding to backend):

```bash
# Health
curl https://brazil.ambern.dev/api/v1/health

# Company lookup
curl -H "X-API-Key: YOUR_KEY" \
     https://brazil.ambern.dev/api/v1/company/11222333000181

# Search with filters
curl -H "X-API-Key: YOUR_KEY" \
     "https://brazil.ambern.dev/api/v1/search?state=SP&status=ATIVA&limit=10"

# Market overview (PRO+)
curl -H "X-API-Key: YOUR_KEY" \
     https://brazil.ambern.dev/api/v1/market/overview

# Get key info
curl -H "X-API-Key: YOUR_KEY" \
     https://brazil.ambern.dev/api/v1/keys/me

# Create a FREE key (no auth)
curl -X POST https://brazil.ambern.dev/api/v1/keys \
     -H "Content-Type: application/json" \
     -d '{"email":"you@example.com","name":"Your Name"}'

# OpenAPI schema
curl https://brazil.ambern.dev/api/openapi.json
```

**Note on FastAPI built-in routes:** `/docs` and `/redoc` are FastAPI's auto-generated Swagger/ReDoc UIs accessible at `https://brazil.ambern.dev/api/docs` and `https://brazil.ambern.dev/api/redoc`. The frontend page `https://brazil.ambern.dev/docs` is the Next.js docs page that embeds Swagger UI pointing at `https://brazil.ambern.dev/api/openapi.json` — these are two separate things.
