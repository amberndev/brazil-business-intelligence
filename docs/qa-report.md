# QA Report — Brazil Business Intelligence (FINAL live re-test, round 2)

- Target: https://brazil.ambern.dev  •  API base (HTTPS): `https://brazil.ambern.dev/api/v1` (Caddy strips `/api`)
- Date: 2026-09-06  •  Mode: read-only (no edits, no deploy)  •  Reviewer: oc-qa (lane F100–F199)
- Method: real Chrome (browser MCP) + curl over HTTPS with a live FREE key (value masked `bbi_UalJ…muC-`)
- Test data: 2 FREE keys created; probe+20260906@ambern.dev **revoked** (DELETE 204, verified 401). qa-testdata-20260906@ambern.dev **left active** — unrecoverable due to F-102 (see F-107; owner must deactivate).

## Prior-blocker verdicts

| ID | Claim | Verdict | Evidence |
|----|-------|---------|----------|
| **F-102** | key-creation UI throws on success → 201 handler | ❌ **NOT FIXED (reopened)** | POST /v1/keys=201 but deployed JS throws `TypeError: Cannot read properties of undefined (reading 'key')`; button stuck on "Creating…", key never shown |
| **F-103** | FREE /v1/search & /v1/company 500 → SQL aligned | ⚠️ **PARTIAL (reopened)** | /v1/company ✅ 200; /v1/search still **500** on default/broad/structured-only queries (200 only for selective `q`) |
| **F-104** | no rate-limit headers → X-RateLimit-* added | ✅ **FIXED (verified)** | all 3 headers present on 200 + 204 authenticated responses |

## (2) All 7 endpoints — FREE key, over HTTPS

| # | Endpoint | Method | Expected (FREE) | Status | Time | X-RateLimit (3)? |
|---|----------|--------|-----------------|--------|------|------------------|
| 1 | /v1/health | GET | 200 (public) | ✅ 200 | 732 ms | n/a (public) — 0/3 |
| 2 | /v1/company/{cnpj} | GET | 200 | ✅ 200 | 763 ms | ✅ 3/3 |
| 3 | /v1/company/{cnpj}/compliance | GET | 403 | ✅ 403 plan_forbidden | 733 ms | 0/3 |
| 4 | /v1/company/{cnpj}/shareholders | GET | 403 | ✅ 403 plan_forbidden | 667 ms | 0/3 |
| 5 | /v1/company/batch | POST | 403 | ✅ 403 plan_forbidden | 745 ms | 0/3 |
| 6 | /v1/search (JSON) | GET | 200 | ❌ **500** (default/broad); 200 only for selective `q` | 500 @ 30–41 s / 200 @ 5–12 s | 3/3 on 200; 0/3 on 500 |
| 7 | /v1/market/overview | GET | 403 | ✅ 403 plan_forbidden | 738 ms | 0/3 |
| + | /v1/search?export=csv | GET | 403 | ✅ 403 plan_forbidden | 723 ms | 0/3 |

**500 count: search endpoint only** (company path clean). Contract expected zero 500s → **FAIL** on search.

## (3) Plan gating — PASS
FREE key correctly 403 `plan_forbidden` on every under-tier endpoint: compliance, shareholders, batch, market/overview, and search `export=csv`. Entitled endpoints (company, health, search-JSON when it runs) not gated. ✅

## (4) 5-page console-error smoke — PASS on load (1 interaction caveat)

| Page | Console errors on load |
|------|------------------------|
| `/` | ✅ none |
| `/docs` | ✅ none (Redocly embed renders all endpoints; base URL correct) |
| `/app/search` | ✅ none (clean "Enter your API key" empty state) |
| `/app/company/[cnpj]` | ✅ none (gated empty state, all §sections present) |
| `/app/keys` (plain load) | ✅ none |

⚠️ Caveat: `/app/keys` throws on the **create action** (F-102) — page loads clean but the create flow crashes.

## (5) /v1/search latency — TWO queries (72M rows)
- `q=banco&limit=3` → **200, 5,068 ms**
- `q=restaurante&state=SP&limit=3` → **200, 12,498 ms**
- (broad/default all 500: `q=comercio` 30.8 s, `sector=comercio` 30.8 s, `has_email=true` 30.8 s, `state=SP` 41.7 s, no-filter 41.4 s, `limit=1` 34.6 s)
- Even successful searches are slow (5–12 s); broad/default ones time out → 500.

## (6) Cleanup — DONE (partial)
- probe+20260906@ambern.dev → `DELETE /v1/keys/me` = **204**; reuse → **401 invalid_api_key**; `GET /keys/me` → 401. ✅ Fully revoked.
- qa-testdata-20260906@ambern.dev → orphaned active (F-107); value lost to F-102 crash; **owner must deactivate manually**.

## Addendum — plus-addressed email
- (a) `probe+20260906@ambern.dev` → POST /v1/keys = **201 ACCEPTED** (plan FREE, limit 50). Plus-addressing is **NOT rejected** on the live deploy — the external probe's 422 was almost certainly the literal `<timestamp>` placeholder (or a duplicate/throttle), not the `+`. Live email regex `^[^@\s]+@[^@\s]+\.[^@\s]{2,}$` permits `+`. **No finding.**
- (b) 422 body **names the field** via stable slug:
  - invalid format → `{"error":{"code":"invalid_email","message":"Provide a valid email address.","status":422}}`
  - missing → `{"error":{"code":"email_required","message":"email is required.","status":422}}`

## Findings (lane F100–F199)
| ID | Sev | Status | Summary |
|----|-----|--------|---------|
| F-102 | alta | reaberto | Key-creation UI throws on 201, hangs on "Creating…", key never shown |
| F-103 | alta | reaberto | /v1/search still 500s on default/broad/structured-only queries (company fixed) |
| F-106 | alta | aberto | Key validate/save broken — validateApiKey() uses the failing /v1/search?limit=1 |
| F-105 | média | aberto | 500 returns plain-text, not the contract error envelope |
| F-107 | média | aberto | F-102 crash strands orphaned active keys (unrecoverable) |
| F-104 | média | verificado | X-RateLimit-* headers present (FIXED) |
| F-108 | baixa | precisa-decisão | No rate-limit headers on 403 (contract wording ambiguous) |

## Release verdict
🔴 **NOT SHIPPABLE.** Three `alta` blockers make the product unusable via the UI: signup (F-102), core search (F-103), and key activation (F-106). F-104 is genuinely fixed; F-103 is only half fixed (company good, search bad).
