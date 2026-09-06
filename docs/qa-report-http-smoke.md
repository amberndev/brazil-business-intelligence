# QA Report — HTTP/Browser Smoke Test · brazil.ambern.dev

**Scope:** READ-ONLY production smoke test of the live site over real HTTPS — browser automation (Chrome, Browser 1) for the 5 spec pages + `curl`/HTTPS for API-level assertions. No mutation performed; no key minted; no secret/key/IP/env value printed. Spec-of-record: `CONTRACT.md` (the file `C:\Users\amber\Downloads\SPEC.md` is NOT the spec — it was overwritten with an unrelated transcript that contains live credentials; see note at bottom).

**Date:** 2026-09-06 · **Reviewer:** oc-qa (pane-63) · **Findings lane:** F100–F199 · **Sibling report:** `qa-report.md` (pane-64, VPS/infra layer, lane F400) — left intact.

**Verdict: FAIL** — backend/API layer is healthy and correct; the **frontend is broken in production** because it ships the dev fallback API URL `http://localhost:8100`. 1 high, 2 medium, 1 low finding.

---

## Required checks (a)–(f)

### (a) All 5 spec pages render with NO console errors
| Route | Render | Console | Result |
|---|---|---|---|
| `/` (Landing) | h1 "Verify Any Brazilian Company in Milliseconds", nav, CTAs "Get API Key — Free"/"View Docs" present | clean | ✅ PASS |
| `/docs` | Redoc panel shows **"Something went wrong... Failed to fetch"**; visible "Base URL: http://localhost:8100/v1" | **2 errors** (`Failed to fetch` ×2, redoc) | ❌ **FAIL** → F-101 |
| `/app/search` | filters (state/sector/size/status/has_debt), results table cols CNPJ·Name·City/UF·Sector·Status·Debt, pagination | clean | ⚠️ PASS* |
| `/app/company/[cnpj]` | header + overview/location/sector/contact/compliance/shareholders sections | clean | ⚠️ PASS* |
| `/app/keys` | apikey form + input + Save Key | clean | ✅ PASS |

\* **PASS only in the unauthenticated state.** Search & Company gate behind "Enter your API key…" and therefore fire **no** API call, so they load without errors. The moment a user saves a valid key they call `http://localhost:8100/v1/...` (same root cause as F-101) and will fail — functionally broken for real use.

### (b) GET /api/v1/health → 200  ✅ PASS
`curl https://brazil.ambern.dev/api/v1/health` → `200`, body exactly `{"status":"ok","db":"ok","redis":"memory-fallback","version":"1.0.0"}` (unwrapped, matches CONTRACT §A.1). `redis":"memory-fallback"` = Redis not wired; in-memory limiter fallback active (allowed by spec).

### (c) Protected endpoint returns 401 WITHOUT an API key  ✅ PASS
- `GET /api/v1/company/11222333000181` (no key) → `401` `{"error":{"code":"missing_api_key",...}}` ✓
- `GET /api/v1/search?limit=1` (no key) → `401 missing_api_key` ✓
- `POST /api/v1/company/batch {"cnpjs":[]}` (no key) → `401` (auth enforced before body validation) ✓
- Invalid key → `401 invalid_api_key` ✓ (distinct code, per CONTRACT §A error table)
- The seeded dev keys (`bbi_dev_*`, `scripts/seed.py`) are **NOT live in prod** → `401 invalid_api_key`. Good: no default credentials in production.

### (d) Plan gating (free vs paid tier)  ⚠️ NOT VERIFIABLE LIVE (no defect observed)
Requires a valid production API key of each tier. I hold none, and minting one via `POST /v1/keys` is a write outside this read-only scope. Code path is present and correct (`backend/app/auth.py:50-66` `require_plan` with `PLAN_ORDER FREE<STARTER<PRO<ENTERPRISE`), but it could not be exercised over live HTTP. **Coverage gap — needs a prod key to close.**

### (e) Rate-limit response headers present & behaving  ⚠️ NOT VERIFIABLE LIVE (no defect observed)
`X-RateLimit-Limit/Remaining/Reset` are only attached to **authenticated** responses and the 429 path (`auth.py:119-129`, `95-99`). Unauthenticated 401s correctly carry none (auth fails before the limiter). Without a valid key I can't produce an authenticated 2xx or reach 429, so header presence/values are unconfirmed live. **Coverage gap — needs a prod key.**

### (f) OpenAPI / docs served  ✅ PASS
- `GET /api/openapi.json` → `200` (OpenAPI 3.1.0, title "Brazil Business Intelligence API" v1.0.0).
- `GET /api/docs` → `200` (Swagger UI). `GET /api/redoc` → `200`.
- Note: `/api/v1/openapi.json` and `/openapi.json` (no `/api`) → 404 (schema lives at `/api/openapi.json`). This is what F-101/F-102 get wrong client-side.

---

## Findings (lane F100–F199)
| ID | Sev | Category | Summary | Status |
|----|-----|----------|---------|--------|
| **F-101** | **alta** | funcional | Prod frontend ships dev fallback `http://localhost:8100`; `/docs` broken + whole authenticated app fails once a key is entered | aberto |
| F-102 | média | funcional | Docs quickstart curl examples omit `/api` prefix → documented URLs 404 | aberto |
| F-103 | média | funcional/seg | Live API exposes 9 endpoints vs 7 in contract; unauthenticated `POST /v1/keys` mints FREE keys | aberto |
| F-104 | baixa | usabilidade | `/app/keys` says free keys are "issued manually" while backend self-serves them | aberto |

Full repro per finding in `TASK/items/F-101.md` … `F-104.md`.

## Severity-ranked confirmed issues
1. **F-101 (HIGH)** — production frontend is non-functional: `/docs` is broken for all visitors and every data page dies the instant a user authenticates, because `NEXT_PUBLIC_API_URL` was not baked into the prod build. Backend is healthy; fix is a frontend rebuild with the prod API URL.
2. **F-103 (MEDIUM)** — open, unauthenticated key-minting endpoint + endpoint set wider than the contract (owner should confirm/lock).
3. **F-102 (MEDIUM)** — the only base URL the docs show users (localhost, and `/v1` without `/api`) does not work; copy-pasted examples 404.
4. **F-104 (LOW)** — signup messaging contradicts actual capability.

## What passed
- Backend liveness (`/api/v1/health` 200, correct shape).
- Auth: 401 `missing_api_key` (no header) and 401 `invalid_api_key` (bad/dev key) — correct codes, error envelope per contract; no default creds in prod.
- Auth enforced before body validation (batch).
- OpenAPI + Swagger UI + Redoc all served (200) at `/api/*`.
- Landing, Search, Company, Keys pages render their DOM/landmarks correctly with zero console errors in the unauthenticated state.
- HTTPS/TLS valid (served via Caddy, `Via: 1.1 Caddy`).

## Coverage gaps (not defects)
- Plan gating (d) and rate-limit headers (e) require a valid production API key of each tier — none available, and minting one is out of read-only scope. Recommend the owner provide a throwaway key per tier for a follow-up authenticated pass.

## SPEC.md note (out of scope but flagged)
`C:\Users\amber\Downloads\SPEC.md` is not the product spec — it is an unrelated shell/chat transcript that appears to contain **live credentials** (DB passwords, a JWT secret, an encryption key, SSH notes). I did not reproduce, store, or transmit any of those values. Per CONTRACT.md's own change-log the owner already flagged this; recommend rotating the exposed secrets and removing the file. CONTRACT.md was used as the spec-of-record instead.
