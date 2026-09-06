# CONTRACT — Brazil Business Intelligence

**This is the single source of truth for the interface between the two parallel builders.**
Both sides MUST obey every name, path, type, and status code here **verbatim**. If you need
something not defined here, add an entry under **Open questions for the owner** — do not invent
a divergent name.

## Ownership split (zero shared files)

| Owner | Owns | Must NOT touch |
|---|---|---|
| **Backend builder** | `backend/` only | `frontend/`, root files |
| **Frontend builder** | `frontend/` only | `backend/`, root files |
| **Integration worker** | root files (`README.md` run section, `deploy/`) | `backend/`, `frontend/` internals |

- Backend: FastAPI, Python 3.11+, `uvicorn`, `asyncpg` (**NO ORM**), port **8100**.
- Frontend: Next.js 14 App Router, TypeScript, Tailwind, shadcn/ui, port **3100**.
- Domain: **brazil.ambern.dev** (never `brazilbusiness.io` — see Open questions #1).
- All product-facing copy is in **English**.

---

## A. API ENDPOINTS (7)

Base path: `/v1`. Auth header `X-API-Key` required on all endpoints **except** `/v1/health`.

### Standard response envelope

Every successful `2xx` (except `/v1/health`) returns:

```json
{
  "data": { ... },
  "meta": {
    "query_time_ms": 0.42,
    "plan": "STARTER",
    "requests_remaining": 1847
  }
}
```

- `meta.query_time_ms` — `float` (DB query wall time).
- `meta.plan` — `string`, one of `FREE|STARTER|PRO|ENTERPRISE`.
- `meta.requests_remaining` — `int`; `-1` means unlimited (ENTERPRISE).

### Standard error envelope

Every non-2xx returns exactly this shape (no `data`, no `meta`):

```json
{
  "error": {
    "code": "invalid_cnpj",
    "message": "CNPJ failed check-digit validation.",
    "status": 422
  }
}
```

- `error.code` — `string`, stable machine slug (see per-endpoint list).
- `error.message` — `string`, human-readable English.
- `error.status` — `int`, mirrors the HTTP status.

**Shared error codes / statuses (apply everywhere):**

| Status | `error.code` | When |
|---|---|---|
| 401 | `missing_api_key` | `X-API-Key` header absent |
| 401 | `invalid_api_key` | key not found / `active = false` |
| 403 | `plan_forbidden` | key valid but plan tier lacks access to this endpoint/field |
| 422 | `invalid_cnpj` | CNPJ malformed or fails check digits |
| 429 | `rate_limit_exceeded` | monthly quota exhausted — response includes header `X-RateLimit-Reset` (RFC 3339 UTC of `reset_at`) |
| 404 | `not_found` | CNPJ not present in database |
| 500 | `internal_error` | unhandled server error |

On **every** authenticated response (success and 429) the backend also sends headers:
`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

---

### 1. `GET /v1/health`  — service liveness (NO auth)

- Params: none.
- **200** response (NOT wrapped in the standard envelope):

```json
{ "status": "ok", "db": "ok", "redis": "memory-fallback", "version": "1.0.0" }
```

- `status`: `string` `"ok"|"degraded"`.
- `db`: `string` `"ok"|"error"`.
- `redis`: `string` `"ok"|"memory-fallback"`.
- `version`: `string`.

---

### 2. `GET /v1/company/{cnpj}`  — full company profile

- Plan gate: **FREE+** (all plans).
- Path param `cnpj`: `string`, accepted with or without mask (`12345678000195` or `12.345.678/0001-95`); backend normalizes to 14 digits and validates check digits before querying.
- `data` shape → TS `CompanyProfile` (§B).
- Errors: `invalid_cnpj` (422), `not_found` (404) + shared auth/rate codes.

### 3. `GET /v1/company/{cnpj}/compliance`  — PGFN debt + CGU sanctions

- Plan gate: **STARTER+** (FREE → 403 `plan_forbidden`).
- Path param `cnpj`: same rules as #2.
- `data` shape → TS `CompanyCompliance` (§B).
- Errors: `invalid_cnpj` (422), `not_found` (404), `plan_forbidden` (403) + shared.

### 4. `GET /v1/company/{cnpj}/shareholders`  — partners/owners

- Plan gate: **STARTER+**.
- Path param `cnpj`: same rules as #2.
- `data` shape → TS `CompanyShareholders` (§B).
- Errors: `invalid_cnpj` (422), `not_found` (404), `plan_forbidden` (403) + shared.

### 5. `POST /v1/company/batch`  — bulk CNPJ lookup (max 50)

- Plan gate: **STARTER+**.
- Request body (`application/json`) → TS `BatchRequest` (§B):

```json
{ "cnpjs": ["12345678000195", "12.345.678/0001-95"] }
```

- `cnpjs`: `string[]`, length **1–50**. >50 → 422 `batch_too_large`; empty → 422 `batch_empty`.
- `data` shape → TS `BatchResponse` (§B): per-CNPJ result carries either `profile` or `error` (invalid/not-found entries do NOT fail the whole batch).
- Rate limiting: **counts as 1 request** against the quota regardless of batch size.
- Errors: `batch_too_large` (422), `batch_empty` (422), `plan_forbidden` (403) + shared.

### 6. `GET /v1/search`  — filtered company search (paginated)

- Plan gate: **FREE+** ("basic search"). `export=csv` is **PRO+** (FREE/STARTER → 403 `plan_forbidden`).
- Query params (all optional unless noted):

| Param | Type | Notes |
|---|---|---|
| `q` | `string` | free text (nome fantasia / razão social) |
| `state` | `string` | UF (`SP`, `RJ`, `MG`…) |
| `city` | `string` | município |
| `sector` | `string` | CNAE (code or description) |
| `size` | `enum` | `MEI\|ME\|EPP\|MEDIO\|GRANDE` |
| `status` | `enum` | `ATIVA\|BAIXADA\|SUSPENSA` |
| `has_debt` | `bool` | only companies with PGFN debt |
| `has_email` | `bool` | only companies with e-mail |
| `has_phone` | `bool` | only companies with mobile phone |
| `page` | `int` | default `1`, min `1` |
| `limit` | `int` | default `20`, max `100` |
| `export` | `enum` | `csv` → returns `text/csv` attachment instead of JSON (**PRO+**) |

- JSON `data` shape → TS `SearchResponse` (§B) with `results: SearchResultRow[]` and a `pagination` block.
- Invalid enum value → 422 `invalid_filter`. `limit>100` is clamped to 100 (not an error).
- Errors: `invalid_filter` (422), `plan_forbidden` (403, for `export=csv` under-tier) + shared.

### 7. `GET /v1/market/overview`  — aggregate totals by state & sector

- Plan gate: **PRO+** (FREE/STARTER → 403 `plan_forbidden`).
- Query params (optional): `state` `string` (filter to one UF), `sector` `string` (filter to one CNAE).
- `data` shape → TS `MarketOverview` (§B).
- Errors: `plan_forbidden` (403) + shared.

---

## B. TypeScript response interfaces (frontend imports these names verbatim)

Put these in `frontend/src/lib/api-types.ts`. Names are **stable contract**.

```ts
// ---- envelope ----
export interface ApiMeta {
  query_time_ms: number;
  plan: PlanTier;
  requests_remaining: number; // -1 = unlimited
}
export interface ApiResponse<T> {
  data: T;
  meta: ApiMeta;
}
export interface ApiError {
  error: { code: string; message: string; status: number };
}
export type PlanTier = "FREE" | "STARTER" | "PRO" | "ENTERPRISE";
export type CompanySize = "MEI" | "ME" | "EPP" | "MEDIO" | "GRANDE";
export type CompanyStatus = "ATIVA" | "BAIXADA" | "SUSPENSA";

// ---- 1. health (unwrapped) ----
export interface HealthResponse {
  status: "ok" | "degraded";
  db: "ok" | "error";
  redis: "ok" | "memory-fallback";
  version: string;
}

// ---- 2. company profile ----
export interface CompanyProfile {
  cnpj: string;                 // 14 digits, unmasked
  cnpj_formatted: string;       // "12.345.678/0001-95"
  razao_social: string;
  nome_fantasia: string | null;
  status: CompanyStatus;
  size: CompanySize | null;
  opened_at: string | null;     // ISO date "YYYY-MM-DD"
  legal_nature: string | null;  // natureza jurídica
  share_capital: number | null; // capital social (BRL)
  location: {
    street: string | null;
    number: string | null;
    complement: string | null;
    district: string | null;    // bairro
    city: string | null;
    state: string | null;       // UF
    zip: string | null;         // CEP
  };
  sector: {
    primary_cnae: { code: string; description: string | null } | null;
    secondary_cnae: { code: string; description: string | null }[];
  };
  contact: {
    phone: string | null;
    email: string | null;
  };
}

// ---- 3. compliance ----
export interface CompanyCompliance {
  cnpj: string;
  pgfn_debt: {
    has_debt: boolean;
    total_amount: number;       // BRL
    records_count: number;
  };
  cgu_sanctions: {
    has_sanctions: boolean;
    count: number;
    items: {
      type: string;             // e.g. sanction category
      description: string | null;
      start_date: string | null;
      end_date: string | null;
    }[];
  };
}

// ---- 4. shareholders ----
export interface Shareholder {
  name: string;
  document: string | null;      // masked/partial only — never full CPF
  role: string | null;          // qualificação do sócio
  participation_pct: number | null;
  since: string | null;         // ISO date
}
export interface CompanyShareholders {
  cnpj: string;
  count: number;
  shareholders: Shareholder[];
}

// ---- 5. batch ----
export interface BatchRequest { cnpjs: string[]; }         // 1..50
export interface BatchItemResult {
  cnpj: string;                                            // normalized input
  profile: CompanyProfile | null;
  error: { code: string; message: string } | null;        // set when profile null
}
export interface BatchResponse {
  count: number;
  results: BatchItemResult[];
}

// ---- 6. search ----
export interface SearchResultRow {
  cnpj: string;
  cnpj_formatted: string;
  name: string;                 // nome fantasia || razão social
  city: string | null;
  state: string | null;         // UF
  sector: string | null;        // primary CNAE description
  status: CompanyStatus;
  has_debt: boolean;            // drives the debt badge
}
export interface Pagination {
  page: number;
  limit: number;
  total: number;                // total matching rows
  total_pages: number;
}
export interface SearchResponse {
  results: SearchResultRow[];
  pagination: Pagination;
}

// ---- 7. market overview ----
export interface MarketOverview {
  total_companies: number;
  by_state: { state: string; count: number }[];
  by_sector: { cnae: string; description: string | null; count: number }[];
}
```

---

## C. PLANS (4) — tiers, limits, gating

| Plan | Price | Monthly quota | Access |
|---|---|---|---|
| **FREE** | $0 | **50 req/mo** | CNPJ lookup (`/v1/company/{cnpj}`), basic search (`/v1/search` JSON) |
| **STARTER** | $79 | **2,000 req/mo** | FREE **+** compliance, shareholders, batch |
| **PRO** | $249 | **15,000 req/mo** | STARTER **+** CSV export (`/v1/search?export=csv`), market overview, e-mail support |
| **ENTERPRISE** | Custom | **Unlimited** (`requests_remaining = -1`) | PRO **+** SLA, IP whitelist, dedicated support |

**Automatic vs manual:** FREE and STARTER activate automatically. PRO and ENTERPRISE → contact form (manual). See stub §G-1.

**Endpoint → minimum plan gate (backend enforces; 403 `plan_forbidden` otherwise):**

| Endpoint | Min plan |
|---|---|
| `GET /v1/health` | none (public) |
| `GET /v1/company/{cnpj}` | FREE |
| `GET /v1/search` (JSON) | FREE |
| `GET /v1/search?export=csv` | PRO |
| `GET /v1/company/{cnpj}/compliance` | STARTER |
| `GET /v1/company/{cnpj}/shareholders` | STARTER |
| `POST /v1/company/batch` | STARTER |
| `GET /v1/market/overview` | PRO |

**Rate limiting:** per API key, monthly, backed by Redis with automatic in-memory fallback when `REDIS_URL` is absent/unreachable. Batch counts as 1 request. On exhaustion → 429 `rate_limit_exceeded` + `X-RateLimit-Reset`. Source of truth for the counter is `product.api_keys` (`requests_this_month`, `requests_limit`, `reset_at`); Redis is the fast-path cache/limiter.

---

## D. FRONTEND PAGES (5)

| Route | Access | Consumes | Renders |
|---|---|---|---|
| `/` | public | none (static stats) | Landing |
| `/docs` | public | `/v1/openapi.json` | API docs (Swagger UI or Redoc embed) + English quickstart |
| `/app/search` | requires API key | `GET /v1/search` | Search + filters + paginated results table |
| `/app/company/[cnpj]` | requires API key | `GET /v1/company/{cnpj}`, `/compliance`, `/shareholders` | Full company profile |
| `/app/keys` | requires "login" (API key present) | (frontend-managed; see §E) | Manage/enter API key |

**DOM landmarks the reviewer checks (use these exact `id`s / roles):**

- **`/`** — `<nav id="site-nav">`; `<section id="hero">` containing `<h1>` "Verify Any Brazilian Company in Milliseconds" and CTA `<a id="cta-get-key">` "Get API Key — Free" + `<a id="cta-view-docs">` "View Docs"; `<section id="stats-bar">` (72M+ / 28M / 6.8M / Updated Monthly); `<section id="use-cases">` (3 cards: Due Diligence, Market Entry, Compliance); `<section id="api-preview">` (code block request+response); `<section id="pricing">` (4-plan table); `<footer id="site-footer">` (Ambern logo + links).
- **`/docs`** — `<main id="api-docs">` hosting the Swagger/Redoc embed.
- **`/app/search`** — `<aside id="search-filters">` (state, sector, size, status, has_debt); `<input id="search-input">`; `<table id="results-table">` with columns CNPJ | Name | City/UF | Sector | Status | Debt badge; each `<tr>` links to `/app/company/[cnpj]`; pagination control `id="results-pagination"`.
- **`/app/company/[cnpj]`** — sections `id="company-header"` (razão social + nome fantasia + status badge), `id="company-overview"`, `id="company-location"`, `id="company-sector"`, `id="company-contact"`, `id="company-compliance"`, `id="company-shareholders"` (`<table>` with participation %).
- **`/app/keys`** — `<form id="apikey-form">` with `<input id="apikey-input">` + save button; shows current plan/quota when a key is loaded.

**Frontend → backend base URL:** `NEXT_PUBLIC_API_URL` (default `http://localhost:8100`). Every authenticated request sends `X-API-Key`. Invalid key → redirect to `/` with a message.

---

## E. API-KEY AUTH CONTRACT

- **Header:** `X-API-Key: <key>` on every `/v1/*` call except `/v1/health`.
- **Key format:** `bbi_` prefix + 32 url-safe base64/hex chars, e.g. `bbi_a1b2c3d4e5f6...`. Treated as an opaque string; backend does not parse meaning from it.
- **Frontend "login":** minimal — user enters key on `/app/keys` (or first visit), stored in `localStorage` under key **`bbi_api_key`**. No external auth provider (no Clerk). The key IS the session.
- **Backend validation:** on each request, look up the key in `product.api_keys`:
  1. row exists AND `active = true` → else 401 (`missing_api_key` / `invalid_api_key`).
  2. resolve `plan` → enforce endpoint gate (403 `plan_forbidden` if under tier).
  3. enforce quota via Redis/in-memory limiter mirrored to `requests_this_month` vs `requests_limit`; increment on success; 429 when exceeded.
- **Product DB table (already specified — backend creates schema `product`):**

```sql
CREATE SCHEMA IF NOT EXISTS product;
CREATE TABLE product.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key TEXT UNIQUE NOT NULL,
    name TEXT,
    email TEXT,
    plan TEXT NOT NULL DEFAULT 'FREE',
    requests_this_month INT DEFAULT 0,
    requests_limit INT DEFAULT 50,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reset_at TIMESTAMPTZ DEFAULT DATE_TRUNC('month', NOW()) + INTERVAL '1 month'
);
CREATE INDEX ON product.api_keys(key);
```

Columns the backend reads/writes for auth: `key`, `plan`, `requests_this_month`, `requests_limit`, `active`, `reset_at`, plus `name`/`email` for the welcome-email hook (§G-3).

---

## F. ENVIRONMENT VARIABLES

Documented in `backend/.env.example`. Credentials live ONLY in env vars — none hardcoded, no real secrets exist yet.

### Backend (`backend/.env.example`)

| Var | Purpose | Example placeholder |
|---|---|---|
| `DATABASE_URL` | Read-only prospecta DB (role `prospecta_readonly`) | `postgresql://USER:PASSWORD@HOST:5432/DBNAME |
| `PRODUCT_DATABASE_URL` | Product DB for `product.api_keys` (role `product_user`) | `postgresql://USER:PASSWORD@HOST:5432/DBNAME |
| `REDIS_URL` | Rate-limit/cache backend; **optional** — in-memory fallback if absent/unreachable | `redis://localhost:6379` |
| `CONTACT_EMAIL` | Contact/from address for hooks (default) | `contact@ambern.dev` |
| `API_ENV` | Runtime env | `production` |
| `CORS_ORIGINS` | Allowed origins (comma-sep) | `https://brazil.ambern.dev,http://localhost:3100` |

### Frontend (`frontend/.env.example`)

| Var | Purpose | Example placeholder |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL | `http://localhost:8100` |
| `NEXT_PUBLIC_SITE_URL` | Canonical site URL (Next metadata, absolute links) | `https://brazil.ambern.dev` |

### CORS / domain

- Allowed origins: `https://brazil.ambern.dev` (prod) + `http://localhost:3100` (dev).
- Allowed methods: `GET, POST, OPTIONS`. Allowed headers: `X-API-Key, Content-Type`.
- Caddy snippet (integration worker, in `deploy/`) reverse-proxies `brazil.ambern.dev` → `127.0.0.1:3100` and its API host → `127.0.0.1:8100`. **Domain is `brazil.ambern.dev`, never `brazilbusiness.io`.**

---

## G. DECLARED STUBS (implement as TODO, owner side noted)

1. **PRO/ENTERPRISE contact form (frontend)** — pricing CTAs for PRO/ENTERPRISE open a contact form that POSTs nothing real yet; wire to `CONTACT_EMAIL` later. `// TODO(frontend): contact-email hook — empty`.
2. **CONTACT_EMAIL email hook (backend)** — no SMTP sending; function exists and no-ops. `# TODO(backend): send via CONTACT_EMAIL — empty`.
3. **Welcome-email hook on key creation (backend)** — no-op stub after inserting an `api_keys` row. `# TODO(backend): welcome email — empty`.
4. **Ambern logo (frontend)** — textual inline **SVG placeholder** (word "Ambern"), not a real asset. `// TODO(frontend): replace with real logo`.
5. **Footer links (frontend)** — configurable but **empty** by default (array of `{label, href}`, ships empty). `// TODO(frontend): footer links`.
6. **CVM endpoint (backend)** — **AMBIGUOUS, see Open questions #4.** The 7 required endpoints do NOT include a CVM endpoint; `cvm.*` tables exist but no route consumes them. Ship the compliance endpoint with **PGFN + CGU only** as specified; do not add a CVM route unless the owner defines one. `# TODO(backend): CVM endpoint undefined — minimal/none pending owner`.

---

## Spec change log

**Re-read of `C:\Users\amber\Downloads\SPEC.md` on 2026-09-05 (owner re-save): the file is NO LONGER the spec.**

- The re-saved file does **not** contain the Brazil Business Intelligence spec. It was overwritten by an unrelated shell/chat transcript (0 matches for any spec marker: endpoints, plans, page routes, FastAPI, Next.js — 134 lines, all off-topic).
- **The transcript contains what appear to be LIVE CREDENTIALS** (Postgres role passwords, a Postiz `POSTGRES_PASSWORD`/`JWT_SECRET`, an n8n `N8N_ENCRYPTION_KEY`, and SSH/sshd notes). None of these values are reproduced here, in the scaffold, or anywhere in this repo — per the owner brief, credentials live only in env vars and no real secrets belong in the codebase.
- **Diff result: no valid spec change.** Because the current file has no extractable spec, CONTRACT.md and the scaffold are **unchanged** and remain based on the original spec read at the start of this task. No endpoints/pages/plans/prohibitions were added, removed, or modified.
- **Action needed from owner:** this looks like an accidental wrong-file save. Please (1) restore the correct `SPEC.md`, and (2) treat the transcript's credentials as exposed — rotate the affected Postgres/Postiz/JWT/n8n secrets and remove the file from `Downloads`. I did not act on, store, or transmit any of those values.

---

## Open questions for the owner

1. **Domain conflict (owner decision wins).** SPEC §4 uses `brazilbusiness.io` (`api.brazilbusiness.io`, `app.brazilbusiness.io`). Owner decision fixes the domain to **brazil.ambern.dev**. Encoded `brazil.ambern.dev` everywhere (CORS, Next metadata, Caddy). Confirm the API subdomain scheme you want (e.g. `brazil.ambern.dev` for the app + a path/subdomain for the API).
2. **Build location (owner decision wins).** SPEC suggests `/opt/brazil-intelligence/api|web/`; owner fixes repo root to `E:\Overclok\brazil-business-intelligence`. Deploy paths on the VPS remain `/opt/brazil-intelligence/...` per SPEC — integration worker maps them.
3. **No dedicated CVM endpoint exists** in the 7 required endpoints, yet `cvm.*` (19 tables) is available data and the owner brief mentions a "CVM endpoint = minimal version if ambiguous." Do you want a new endpoint (e.g. `GET /v1/company/{cnpj}/securities`)? If so it would be endpoint #8 and needs a plan gate + response shape. Left OUT of the contract pending your decision (compliance stays PGFN+CGU).
4. **Exact DB column mapping** (receita.busca/empresas/estabelecimentos/socios, pgfn, cgu → contract fields) is left to the backend builder from the live schema; the contract fixes the **response** field names, not source column names. Flag if any contract field has no source column (e.g. `share_capital`, secondary CNAE, CGU sanction dates).
5. **"Export CSV" gate** — placed at PRO+ per SPEC §3 ("PRO + Export CSV"). Confirm STARTER should NOT get CSV export.
