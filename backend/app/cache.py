"""
Cache / rate-limit backend.

Seam interface — five async methods: get / set / incr / expire / delete.

RedisWithFallback tries Redis first; on every failed op it silently falls
back to the in-process InMemoryCache and logs at DEBUG level.
If REDIS_URL is empty/absent, only InMemoryCache is used (no Redis import error).

Worker B wiring: `cache` is now a RedisWithFallback instance; the lifespan
in db.py calls cache.startup() to log which path is active at boot time.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

# ── In-memory backend (always available) ──────────────────────────────────────

class InMemoryCache:
    """Thread-safe (asyncio) in-memory cache with optional TTL."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    def _expired(self, expires_at: Optional[float]) -> bool:
        return expires_at is not None and time.monotonic() > expires_at

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if self._expired(expires_at):
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            expires_at = time.monotonic() + ttl if ttl is not None else None
            self._store[key] = (value, expires_at)

    async def incr(self, key: str) -> int:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None or self._expired(entry[1]):
                new_val = 1
                self._store[key] = (new_val, None)
            else:
                new_val = (entry[0] or 0) + 1
                self._store[key] = (new_val, entry[1])
            return new_val

    async def expire(self, key: str, ttl: int) -> None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is not None:
                self._store[key] = (entry[0], time.monotonic() + ttl)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def setnx(self, key: str, value: Any) -> bool:
        """Set key to value only if it does not already exist. Returns True if set."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None or self._expired(entry[1]):
                self._store.pop(key, None)
                self._store[key] = (value, None)
                return True
            return False


# ── Redis-backed cache with fallback ─────────────────────────────────────────

class RedisWithFallback:
    """
    Redis-first cache that falls back to InMemoryCache transparently.

    Startup logging (called from db.lifespan):
        await cache.startup()   → logs "Cache: Redis active" or "Cache: in-memory fallback"
    """

    def __init__(self, redis_url: str = "") -> None:
        self._memory = InMemoryCache()
        self._redis: Any = None  # redis.asyncio.Redis or None
        self._url = redis_url

        if redis_url:
            try:
                import redis.asyncio as aioredis  # type: ignore
                self._redis = aioredis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    retry_on_timeout=False,
                )
            except Exception as exc:  # pragma: no cover
                log.warning("Cache: Redis init error (%s) — using in-memory fallback", exc)

    async def startup(self) -> None:
        """Log active backend. Call once from lifespan after pool is ready."""
        if self._redis is None:
            log.info("Cache backend: in-memory fallback (REDIS_URL not set)")
            return
        try:
            await self._redis.ping()
            log.info("Cache backend: Redis at %s", self._url.split("@")[-1])
        except Exception as exc:
            log.warning("Cache backend: Redis unreachable (%s) — in-memory fallback active", exc)

    # ── helpers ────────────────────────────────────────────────────────────────

    async def _r_get(self, key: str) -> Optional[Any]:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return raw
        except Exception as exc:
            log.debug("Cache: Redis get failed (%s)", exc)
            return None

    async def _r_set(self, key: str, value: Any, ttl: Optional[int]) -> bool:
        if self._redis is None:
            return False
        try:
            serialized = json.dumps(value)
            kwargs: dict = {"ex": ttl} if ttl else {}
            await self._redis.set(key, serialized, **kwargs)
            return True
        except Exception as exc:
            log.debug("Cache: Redis set failed (%s)", exc)
            return False

    async def _r_incr(self, key: str) -> Optional[int]:
        if self._redis is None:
            return None
        try:
            return int(await self._redis.incr(key))
        except Exception as exc:
            log.debug("Cache: Redis incr failed (%s)", exc)
            return None

    async def _r_expire(self, key: str, ttl: int) -> bool:
        if self._redis is None:
            return False
        try:
            await self._redis.expire(key, ttl)
            return True
        except Exception as exc:
            log.debug("Cache: Redis expire failed (%s)", exc)
            return False

    async def _r_delete(self, key: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(key)
        except Exception as exc:
            log.debug("Cache: Redis delete failed (%s)", exc)

    async def _r_setnx(self, key: str, value: Any) -> Optional[bool]:
        """SET key value NX via Redis. Returns True if set, False if existed, None on error."""
        if self._redis is None:
            return None
        try:
            serialized = json.dumps(value)
            result = await self._redis.set(key, serialized, nx=True)
            return result is not None  # Redis returns None if key existed
        except Exception as exc:
            log.debug("Cache: Redis setnx failed (%s)", exc)
            return None

    # ── public interface ───────────────────────────────────────────────────────

    async def get(self, key: str) -> Optional[Any]:
        val = await self._r_get(key)
        if val is not None:
            return val
        return await self._memory.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if not await self._r_set(key, value, ttl):
            await self._memory.set(key, value, ttl)

    async def incr(self, key: str) -> int:
        result = await self._r_incr(key)
        if result is not None:
            return result
        return await self._memory.incr(key)

    async def expire(self, key: str, ttl: int) -> None:
        if not await self._r_expire(key, ttl):
            await self._memory.expire(key, ttl)

    async def delete(self, key: str) -> None:
        await self._r_delete(key)
        await self._memory.delete(key)

    async def setnx(self, key: str, value: Any) -> bool:
        """Set key to value only if not exists. Returns True if this call set it."""
        result = await self._r_setnx(key, value)
        if result is not None:
            return result
        return await self._memory.setnx(key, value)


# ── Module-level singleton ─────────────────────────────────────────────────────
# Imported by auth.py and any future modules that need caching.
# Initialised here; startup() is called from db.lifespan so the log fires at boot.

def _build_cache() -> RedisWithFallback:
    try:
        from .config import settings  # late import avoids circular at module load
        return RedisWithFallback(settings.redis_url)
    except Exception:  # pragma: no cover
        return RedisWithFallback("")


cache: RedisWithFallback = _build_cache()
