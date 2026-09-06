# Brazil Business Intelligence

> **Built by [Ambern](https://ambern.dev)**

Instant access to 72M+ Brazilian company records via a production-grade REST API and dashboard — built for due diligence, market entry, and compliance workflows.

**Live demo:** [https://brazil.ambern.dev](https://brazil.ambern.dev)

---

## What it is

A commercial API and web dashboard over the complete Brazilian federal company registry (Receita Federal), PGFN federal debt, and CGU sanctions data. The backend serves structured, normalized company data at millisecond latency; the dashboard gives non-technical users a point-and-click interface over the same data.

- **72M+ company records** — full Receita Federal registry, updated monthly
- **API:** FastAPI + asyncpg (no ORM), Python 3.11+ — port 8100
- **Dashboard:** Next.js 14 App Router, TypeScript, Tailwind, shadcn/ui — port 3100
- **Database:** PostgreSQL 17, two schemas: `receita` (source data) + `product` (API keys, quotas)
- **Infrastructure:** systemd + Caddy on a single VPS, zero-downtime restarts

---

## Architecture

```
Browser ──► https://brazil.ambern.dev/...
                │
                ▼
          Caddy (TLS termination, reverse proxy)
           ├── /api/* ──► FastAPI uvicorn 127.0.0.1:8100
           └── /*     ──► Next.js   127.0.0.1:3100
                │
                ▼
         PostgreSQL 17 (worbita DB)
          ├── receita.*   — source: empresas, estabelecimentos, socios, pgfn, cgu
          └── product.*   — api_keys, quotas, rate-limit state
                │
                ▼
         Redis (rate-limit fast path, optional)
         ── in-memory fallback when REDIS_URL absent/unreachable
```

---

## API overview

Base URL (production): `https://brazil.ambern.dev/api`  
Auth: `X-API-Key: <key>` on every call except `/v1/health`.

Every authenticated `2xx` response is wrapped:

```json
{
  "data": { "..." : "..." },
  "meta": { "query_time_ms": 0.42, "plan": "STARTER", "requests_remaining": 1847 }
}
```

### The 7 contract endpoints

| # | Method | Path | Min plan | Description |
|---|--------|------|----------|-------------|
| 1 | `GET` | `/v1/health` | Public | Service liveness — no auth |
| 2 | `GET` | `/v1/company/{cnpj}` | FREE | Full company profile |
| 3 | `GET` | `/v1/company/{cnpj}/compliance` | STARTER | PGFN debt + CGU sanctions |
| 4 | `GET` | `/v1/company/{cnpj}/shareholders` | STARTER | Partners / owners |
| 5 | `POST` | `/v1/company/batch` | STARTER | Bulk lookup, max 50 CNPJs (counts as 1 request) |
| 6 | `GET` | `/v1/search` | FREE (JSON) / PRO (CSV) | Filtered, paginated company search |
| 7 | `GET` | `/v1/market/overview` | PRO | Aggregate totals by state and sector |

### Key management

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/keys` | None | Self-serve FREE key creation |
| `GET` | `/v1/keys/me` | Any key | Inspect your key's plan and quota |
| `DELETE` | `/v1/keys/me` | Any key | Revoke your key |

### curl examples by plan tier

**FREE** — company lookup:

```bash
curl -H "X-API-Key: bbi_your_free_key" \
     https://brazil.ambern.dev/api/v1/company/12345678000195
```

**STARTER** — shareholders + batch:

```bash
# Shareholders
curl -H "X-API-Key: bbi_your_starter_key" \
     https://brazil.ambern.dev/api/v1/company/12345678000195/shareholders

# Batch (up to 50 CNPJs, counts as 1 request)
curl -X POST -H "X-API-Key: bbi_your_starter_key" \
     -H "Content-Type: application/json" \
     -d '{"cnpjs":["12345678000195","98765432000100"]}' \
     https://brazil.ambern.dev/api/v1/company/batch
```

**PRO** — CSV export + market overview:

```bash
# CSV export
curl -H "X-API-Key: bbi_your_pro_key" \
     "https://brazil.ambern.dev/api/v1/search?state=SP&size=ME&export=csv" \
     -o companies.csv

# Market overview
curl -H "X-API-Key: bbi_your_pro_key" \
     https://brazil.ambern.dev/api/v1/market/overview
```

---

## Plans

| Plan | Price | Monthly quota | Endpoints unlocked |
|------|-------|---------------|--------------------|
| **Free** | $0 | 50 req/mo | CNPJ lookup, basic search (JSON) |
| **Starter** | $79/mo | 2,000 req/mo | Free + compliance, shareholders, batch |
| **Pro** | $249/mo | 15,000 req/mo | Starter + CSV export, market overview, email support |
| **Enterprise** | Custom | Unlimited | Pro + SLA, IP whitelist, dedicated support |

Free and Starter activate automatically. Pro and Enterprise require manual activation — [contact us](mailto:vinicius@ambern.dev).

---

## Security & operations

- **API keys** — `bbi_` prefix + 32 url-safe characters; validated per-request against `product.api_keys`; fully revocable.
- **Plan gating** — enforced server-side on every request; 403 `plan_forbidden` on under-tier access.
- **Rate limiting** — per-key monthly quota, Redis fast path with automatic in-memory fallback. On exhaustion: 429 + `X-RateLimit-Reset` header (RFC 3339 UTC). `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` sent on every authenticated response.
- **No secrets in repo** — all credentials live in env vars; `.env` is gitignored. See `backend/.env.example` for the full variable list.
- **Zero-downtime restarts** — `systemctl reload bbi-api` / `bbi-web`; systemd `Restart=on-failure` with a 5 s delay.

---

## Local development

### Prerequisites

- Python 3.11+ (3.12 recommended)
- Node.js 22
- Docker + Docker Compose (for a local Postgres instance)

### Backend

```bash
# 1. Start local Postgres (port 5433)
docker compose -f backend/docker-compose.dev.yml up -d

# 2. Create virtualenv and install deps
cd backend
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure env
cp .env.example .env
# Edit .env — set DATABASE_URL to the local Postgres from step 1

# 4. Seed schema + fake data
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5433/DBNAME \
    python scripts/seed.py

# 5. Start API
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```

API available at `http://localhost:8100`. Swagger UI at `http://localhost:8100/docs`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local        # NEXT_PUBLIC_API_URL defaults to http://localhost:8100
npm run dev
```

Dashboard available at `http://localhost:3100`.

---

## Deployment

### Prerequisites

- SSH alias `worbita-dados` in `~/.ssh/config` (or set `BBI_SSH_ALIAS`)
- `rsync` available on the local machine

```bash
export BBI_SSH_ALIAS=worbita-dados   # default; can be omitted
bash deploy/deploy.sh
```

The script is idempotent — safe to re-run on subsequent deploys.

### What `deploy.sh` does

1. `rsync` repo to `/opt/brazil-business-intelligence` on the VPS
2. Creates Python venv and installs `requirements.txt`
3. `npm ci && next build` in `frontend/`
4. Installs and binds Redis to `127.0.0.1:6379`
5. Derives `DATABASE_URL` from `RECEITA_DATABASE_URL` in `/opt/worbita/app/.env` — never logged
6. Writes `/opt/brazil-business-intelligence/.env` (chmod 600)
7. Applies `backend/migrations/001_product_schema.sql` (idempotent DDL)
8. Installs/restarts `bbi-api.service` and `bbi-web.service` via systemd
9. Caddy DNS guard: installs Caddy snippet when `brazil.ambern.dev` resolves to the VPS IP; otherwise stages and prints an escalation notice
10. Smoke checks on `:8100/v1/health` and `:3100`

### Deploy artifacts (`deploy/`)

| File | Purpose |
|------|---------|
| `bbi-api.service` | systemd unit — uvicorn backend, `127.0.0.1:8100` |
| `bbi-web.service` | systemd unit — Next.js production server, `127.0.0.1:3100` |
| `Caddyfile.brazil.snippet` | Caddy reverse-proxy block for `brazil.ambern.dev` |
| `deploy.sh` | Idempotent deploy script |

**Caddy snippet (excerpt):**

```caddy
brazil.ambern.dev {
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy 127.0.0.1:8100
    }
    handle {
        reverse_proxy 127.0.0.1:3100
    }
}
```

---

## Testing

### Backend — 74 pytest tests

```bash
cd backend
python -m pytest tests/ -v
```

Tests cover: CNPJ validation, all 7 contract endpoints, plan gating, rate-limit enforcement, batch edge cases, and key-management routes. All mocked at the DB layer — no live Postgres required for tests.

### Frontend — Playwright page checks

```bash
cd frontend
npx playwright test
```

Smoke-tests the key pages (`/`, `/docs`, `/app/search`, `/app/company/[cnpj]`, `/app/keys`) against landmark IDs defined in [docs/CONTRACT.md](./docs/CONTRACT.md).

---

## Roadmap (declared stubs)

These features are stubbed in the codebase and ready to be wired up:

- **Welcome email on key creation** — hook exists in the backend, no-ops until SMTP is configured (`# TODO(backend): welcome email`).
- **PRO/Enterprise contact form** — pricing CTAs collect intent; POST target is a stub (`// TODO(frontend): contact-email hook`).
- **Contact routing** — `CONTACT_EMAIL` is read from env on both sides; routing logic is a stub pending SMTP integration.
- **Role separation** — current DB role has read + write; a read-only role for the receita schema is planned for hardening.

---

## License

All rights reserved. This software is proprietary. Contact us to license it or to commission similar custom development for your business.

---

## Work with us

Ambern builds production-grade data infrastructure and APIs — databases, backends, dashboards, and integrations. If you need something like this built for your own data, we are available for custom development engagements.

- **Website:** [https://ambern.dev](https://ambern.dev)
- **Email:** [vinicius@ambern.dev](mailto:vinicius@ambern.dev)
