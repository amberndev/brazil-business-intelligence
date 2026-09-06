"""Tests for cache module: InMemoryCache and RedisWithFallback fallback behavior."""
from __future__ import annotations

import asyncio

import pytest

from app.cache import InMemoryCache, RedisWithFallback


# ── InMemoryCache ──────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_inmemory_set_get():
    c = InMemoryCache()
    await c.set("k", "hello")
    assert await c.get("k") == "hello"


@pytest.mark.anyio
async def test_inmemory_get_missing():
    c = InMemoryCache()
    assert await c.get("nope") is None


@pytest.mark.anyio
async def test_inmemory_incr():
    c = InMemoryCache()
    assert await c.incr("counter") == 1
    assert await c.incr("counter") == 2
    assert await c.incr("counter") == 3


@pytest.mark.anyio
async def test_inmemory_setnx():
    c = InMemoryCache()
    result1 = await c.setnx("nx", 42)
    assert result1 is True
    assert await c.get("nx") == 42
    # Second call: key exists → False, value unchanged
    result2 = await c.setnx("nx", 99)
    assert result2 is False
    assert await c.get("nx") == 42


@pytest.mark.anyio
async def test_inmemory_delete():
    c = InMemoryCache()
    await c.set("x", 42)
    await c.delete("x")
    assert await c.get("x") is None


@pytest.mark.anyio
async def test_inmemory_expire_ttl():
    """Keys with a very short TTL expire after their window."""
    c = InMemoryCache()
    await c.set("short", "v", ttl=0)  # TTL=0 means already expired
    # monotonic comparison: ttl=0 sets expiry to now, so it expires immediately
    assert await c.get("short") is None


# ── RedisWithFallback — no Redis URL → pure in-memory ─────────────────────────

@pytest.mark.anyio
async def test_fallback_no_url_set_get():
    """With no REDIS_URL, RedisWithFallback uses in-memory transparently."""
    c = RedisWithFallback("")
    await c.set("a", 10)
    assert await c.get("a") == 10


@pytest.mark.anyio
async def test_fallback_no_url_incr():
    c = RedisWithFallback("")
    assert await c.incr("ctr") == 1
    assert await c.incr("ctr") == 2


@pytest.mark.anyio
async def test_fallback_no_url_delete():
    c = RedisWithFallback("")
    await c.set("d", "bye")
    await c.delete("d")
    assert await c.get("d") is None


@pytest.mark.anyio
async def test_fallback_no_url_expire():
    """expire() on in-memory path doesn't raise."""
    c = RedisWithFallback("")
    await c.set("e", "v")
    await c.expire("e", 3600)


@pytest.mark.anyio
async def test_fallback_no_url_setnx():
    """setnx works on fallback: first call sets (True), second is no-op (False)."""
    c = RedisWithFallback("")
    r1 = await c.setnx("nx_key", 100)
    assert r1 is True
    assert await c.get("nx_key") == 100
    r2 = await c.setnx("nx_key", 200)
    assert r2 is False
    assert await c.get("nx_key") == 100  # unchanged


@pytest.mark.anyio
async def test_fallback_bad_url_no_crash():
    """Invalid Redis URL falls back gracefully — no crash, ops still work."""
    c = RedisWithFallback("redis://127.0.0.1:19999/0")  # nothing listening there
    # startup() should log warning, not raise
    await c.startup()
    # ops fall through to in-memory silently
    await c.set("fb", "ok")
    assert await c.get("fb") == "ok"
    assert await c.incr("fb_ctr") == 1


@pytest.mark.anyio
async def test_fallback_startup_no_url():
    """startup() with no URL logs in-memory path — no exception."""
    c = RedisWithFallback("")
    await c.startup()  # should not raise


@pytest.mark.anyio
async def test_rate_limit_pattern():
    """Simulate the rate-limit increment pattern used in auth.py."""
    c = RedisWithFallback("")
    key = "ratelimit:test-key-uuid-123"
    # First request in the month
    count = await c.incr(key)
    assert count == 1
    await c.expire(key, 30 * 24 * 3600)
    # Subsequent requests
    for i in range(2, 6):
        count = await c.incr(key)
        assert count == i
