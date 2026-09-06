"""
X-API-Key authentication + plan gating + rate-limit enforcement.

Rate-limit seam: `check_rate_limit` and `record_usage` both call `cache.*`
from app.cache. Worker B swaps cache → Redis; no changes needed here.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, Response

from .cache import cache
from .db import get_pool

PLAN_ORDER: dict[str, int] = {"FREE": 0, "STARTER": 1, "PRO": 2, "ENTERPRISE": 3}


async def get_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict[str, Any]:
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail={"code": "missing_api_key", "message": "X-API-Key header is required.", "status": 401},
        )

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::text AS id, key, plan,
                   requests_this_month, requests_limit,
                   active, reset_at, name, email
            FROM product.api_keys
            WHERE key = $1
            """,
            x_api_key,
        )

    if row is None or not row["active"]:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_api_key", "message": "API key not found or inactive.", "status": 401},
        )

    return dict(row)


def require_plan(min_plan: str):
    """Dependency factory: validates key AND enforces plan gate."""

    async def _checker(key_info: dict[str, Any] = Depends(get_api_key)) -> dict[str, Any]:
        plan = key_info.get("plan", "FREE")
        if PLAN_ORDER.get(plan, -1) < PLAN_ORDER.get(min_plan, 999):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "plan_forbidden",
                    "message": f"This endpoint requires the {min_plan} plan or higher.",
                    "status": 403,
                },
            )
        return key_info

    return _checker


async def check_rate_limit(key_info: dict[str, Any]) -> int:
    """
    Atomic rate-limit check + increment (FINDING 3).

    Algorithm:
      1. Seed cache from DB via SETNX (atomic: only first caller sets the value).
      2. If this is the first access in the window, set expiry = seconds until reset_at.
      3. Atomically INCR. If new_count > limit: raise 429.
      4. Return requests_remaining AFTER this request (pre-decremented — callers
         should NOT subtract 1 again; after_usage() is now an identity function).

    Multi-worker correct: Redis SETNX and INCR are individually atomic; the
    two-op sequence is safe because a race on SETNX means at most one extra
    increment on cold start (both read the same DB value), which is acceptable
    for a monthly quota.

    Returns -1 for ENTERPRISE (unlimited).
    """
    if key_info["plan"] == "ENTERPRISE":
        return -1

    key_id   = key_info["id"]
    limit    = key_info["requests_limit"]
    reset_at = key_info["reset_at"]
    cache_key = f"ratelimit:{key_id}"

    # Seed from DB value (SETNX — no-op if key already exists in Redis/memory)
    seeded = await cache.setnx(cache_key, key_info["requests_this_month"])
    if seeded and reset_at:
        now = datetime.now(timezone.utc)
        ttl = max(60, math.ceil((reset_at - now).total_seconds()))
        await cache.expire(cache_key, ttl)

    # Atomically increment and get the new count for this window
    new_count = await cache.incr(cache_key)

    if new_count > limit:
        reset_str = reset_at.isoformat() if reset_at else ""
        raise HTTPException(
            status_code=429,
            detail={"code": "rate_limit_exceeded", "message": "Monthly quota exhausted.", "status": 429},
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": reset_str,
            },
        )

    return limit - new_count


async def record_usage(key_info: dict[str, Any]) -> int:
    """No-op: usage is already atomically recorded inside check_rate_limit."""
    return 0


def set_ratelimit_headers(
    response: Response,
    key_info: dict[str, Any],
    requests_remaining: int,
) -> None:
    limit = key_info["requests_limit"]
    reset_at = key_info["reset_at"]
    reset_str = reset_at.isoformat() if reset_at else ""
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, requests_remaining))
    response.headers["X-RateLimit-Reset"] = reset_str


def after_usage(requests_remaining: int) -> int:
    """Identity: check_rate_limit now returns the post-increment remaining directly."""
    return requests_remaining


def make_meta(key_info: dict[str, Any], requests_remaining: int, query_time_ms: float) -> dict:
    return {
        "query_time_ms": round(query_time_ms, 3),
        "plan": key_info["plan"],
        "requests_remaining": requests_remaining,
    }
