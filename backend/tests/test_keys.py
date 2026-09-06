"""Tests for key management endpoints: POST /v1/keys, GET /v1/keys/me, DELETE /v1/keys/me."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

from tests.conftest import make_key_row, make_mock_conn, make_test_client

_PRO_KEY = make_key_row(plan="PRO", requests_limit=15000)


def _generated_row(email: str = "test@example.com"):
    return {
        "id":                   str(uuid.uuid4()),
        "key":                  "bbi_generated_key_test_0000000000",
        "name":                 "Test User",
        "email":                email,
        "plan":                 "FREE",
        "requests_this_month":  0,
        "requests_limit":       50,
        "active":               True,
        "reset_at":             datetime(2026, 10, 1, tzinfo=timezone.utc),
    }


# ── Success path ───────────────────────────────────────────────────────────────

def test_generate_key_success():
    """POST /v1/keys creates a FREE key (unauthenticated)."""
    gen_row = _generated_row()
    conn = make_mock_conn()
    conn.fetchval = AsyncMock(return_value=None)   # no duplicate
    conn.fetchrow = AsyncMock(return_value=gen_row)
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.post("/v1/keys", json={"name": "Test User", "email": "test@example.com"})
    assert resp.status_code == 201
    body = resp.json()
    assert "key" in body
    assert body["key"].startswith("bbi_")
    assert body["plan"] == "FREE"
    assert "message" in body


# ── Email validation (FINDING 2 — 422) ────────────────────────────────────────

def test_generate_key_missing_email():
    """POST /v1/keys without email returns 422 email_required."""
    conn = make_mock_conn()
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.post("/v1/keys", json={"name": "No Email"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "email_required"


def test_generate_key_invalid_email():
    """POST /v1/keys with bad email returns 422 invalid_email."""
    conn = make_mock_conn()
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.post("/v1/keys", json={"email": "not-an-email"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_email"


def test_generate_key_invalid_email_no_tld():
    """Email with no TLD segment fails validation."""
    conn = make_mock_conn()
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.post("/v1/keys", json={"email": "user@nodot"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_email"


# ── Duplicate-email check (FINDING 2 — 409) ───────────────────────────────────

def test_generate_key_duplicate_email():
    """POST /v1/keys when active FREE key already exists for email → 409."""
    existing_id = str(uuid.uuid4())
    conn = make_mock_conn()
    conn.fetchval = AsyncMock(return_value=existing_id)  # duplicate found
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.post("/v1/keys", json={"email": "taken@example.com"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "duplicate_key"


# ── IP throttle (FINDING 2 — 429) ─────────────────────────────────────────────

def test_generate_key_ip_throttled():
    """POST /v1/keys when IP has exceeded 5/hour → 429 create_throttled."""
    from app import cache as cache_module

    # Patch cache.incr to simulate 6 prior calls (over the 5/hour limit)
    async def _incr_over_limit(key: str) -> int:
        return 6  # beyond the 5/hour cap

    conn = make_mock_conn()
    with make_test_client(conn=conn) as (tc, _):
        with patch.object(cache_module.cache, "incr", _incr_over_limit):
            resp = tc.post("/v1/keys", json={"email": "throttled@example.com"})
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "create_throttled"


def test_generate_key_ip_throttle_uses_fallback():
    """IP throttle works via in-memory cache when Redis is absent (fallback path)."""
    from app.cache import InMemoryCache, RedisWithFallback

    fallback = RedisWithFallback("")  # no Redis URL → pure in-memory
    conn = make_mock_conn()
    conn.fetchval = AsyncMock(return_value=None)   # no duplicate
    conn.fetchrow = AsyncMock(return_value=_generated_row())

    from app import cache as cache_module

    with make_test_client(conn=conn) as (tc, _):
        with patch.object(cache_module, "cache", fallback):
            # 5 requests should succeed
            for _ in range(5):
                resp = tc.post("/v1/keys", json={"email": f"user{_}@example.com"})
                # Note: duplicate check sees None for each unique email mock
                # Just verify no 429 on first 5 attempts from this IP
            # 6th attempt over limit
            resp = tc.post("/v1/keys", json={"email": "user6@example.com"})
    # The 6th should be throttled
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "create_throttled"


# ── GET /v1/keys/me ───────────────────────────────────────────────────────────

def test_get_key_me_success():
    """GET /v1/keys/me returns key info for the authenticated key."""
    pro_row = {**_PRO_KEY, "id": str(uuid.uuid4())}
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(side_effect=[pro_row, pro_row])
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.get("/v1/keys/me", headers={"X-API-Key": pro_row["key"]})
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert "key_prefix" in body
    assert body["plan"] == "PRO"
    assert "requests_this_month" in body
    assert "requests_limit" in body
    assert pro_row["key"] not in str(body)


def test_get_key_me_missing_auth():
    """GET /v1/keys/me without header returns 401."""
    conn = make_mock_conn(fetchrow_return=None)
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.get("/v1/keys/me")
    assert resp.status_code == 401


# ── DELETE /v1/keys/me ────────────────────────────────────────────────────────

def test_revoke_key_success():
    """DELETE /v1/keys/me deactivates the key and returns 204."""
    pro_row = {**_PRO_KEY}
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(return_value=pro_row)
    conn.execute  = AsyncMock(return_value=None)
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.delete("/v1/keys/me", headers={"X-API-Key": pro_row["key"]})
    assert resp.status_code == 204
    conn.execute.assert_called_once()


def test_revoke_key_missing_auth():
    """DELETE /v1/keys/me without header returns 401."""
    conn = make_mock_conn(fetchrow_return=None)
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.delete("/v1/keys/me")
    assert resp.status_code == 401


# ── F-104: rate-limit headers on every authenticated response ─────────────────

def test_get_key_me_ratelimit_headers():
    """GET /v1/keys/me must return X-RateLimit-* headers (F-104)."""
    pro_row = {**_PRO_KEY, "id": str(uuid.uuid4())}
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(side_effect=[pro_row, pro_row])
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.get("/v1/keys/me", headers={"X-API-Key": pro_row["key"]})
    assert resp.status_code == 200
    assert "X-RateLimit-Limit"     in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset"     in resp.headers
    assert int(resp.headers["X-RateLimit-Limit"]) == pro_row["requests_limit"]


def test_revoke_key_ratelimit_headers():
    """DELETE /v1/keys/me must return X-RateLimit-* headers (F-104)."""
    pro_row = {**_PRO_KEY}
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(return_value=pro_row)
    conn.execute  = AsyncMock(return_value=None)
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.delete("/v1/keys/me", headers={"X-API-Key": pro_row["key"]})
    assert resp.status_code == 204
    assert "X-RateLimit-Limit"     in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset"     in resp.headers
