"""
API-key management endpoints (not in the 7 contract endpoints, but needed
by the frontend /app/keys page and for self-service FREE/STARTER sign-up).

  POST   /v1/keys        — generate a new key (FREE self-serve, no auth required)
  GET    /v1/keys/me     — return current key info (requires X-API-Key)
  DELETE /v1/keys/me     — revoke (deactivate) current key (requires X-API-Key)

POST /v1/keys security:
  - Email is required and validated (422 on bad format).
  - One active FREE key per email address (409 on duplicate).
  - IP-based creation throttle: 5 requests/hour per client IP (429).
"""
from __future__ import annotations

import math
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from ..auth import get_api_key
from ..cache import cache
from ..db import get_pool
from ..hooks import send_welcome_email

router = APIRouter(tags=["keys"])

_PLAN_LIMITS = {"FREE": 50, "STARTER": 2000, "PRO": 15000, "ENTERPRISE": -1}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

_IP_THROTTLE_LIMIT = 5        # max key creations per IP per hour
_IP_THROTTLE_TTL   = 3600     # 1 hour in seconds


def _generate_raw_key() -> str:
    return "bbi_" + secrets.token_urlsafe(24)


def _key_info_response(row: Any) -> dict:
    reset_raw = row["reset_at"]
    return {
        "id":                   str(row["id"]),
        "key_prefix":           str(row["key"])[:12] + "...",
        "name":                 row["name"],
        "email":                row["email"],
        "plan":                 row["plan"],
        "requests_this_month":  int(row["requests_this_month"]),
        "requests_limit":       int(row["requests_limit"]),
        "reset_at":             reset_raw.isoformat() if reset_raw else None,
        "active":               bool(row["active"]),
    }


async def _check_ip_throttle(ip: str) -> None:
    """Raises 429 if this IP has exceeded the creation rate limit (5/hour)."""
    cache_key = f"create_ip:{ip}"
    count = await cache.incr(cache_key)
    if count == 1:
        await cache.expire(cache_key, _IP_THROTTLE_TTL)
    if count > _IP_THROTTLE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "create_throttled",
                "message": "Too many key-creation requests from this IP. Retry in 1 hour.",
                "status": 429,
            },
        )


@router.post("/keys", status_code=201, response_model=None)
async def generate_key(
    request: Request,
    body: dict[str, Any] = Body(default={}),
) -> JSONResponse:
    """Self-serve key generation for FREE plan (no X-API-Key auth required)."""
    # ── IP throttle (FINDING 2) ──────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    await _check_ip_throttle(client_ip)

    # ── Email required + validate (FINDING 2) ────────────────────────────────
    email: Optional[str] = body.get("email")
    if not email:
        raise HTTPException(
            status_code=422,
            detail={"code": "email_required", "message": "email is required.", "status": 422},
        )
    if not _EMAIL_RE.match(email.strip()):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_email", "message": "Provide a valid email address.", "status": 422},
        )
    email = email.strip().lower()

    name: Optional[str] = body.get("name")

    pool = await get_pool()
    async with pool.acquire() as conn:
        # ── Duplicate-email check (FINDING 2): one active FREE key per email ─
        existing = await conn.fetchval(
            "SELECT id FROM product.api_keys WHERE email = $1 AND plan = 'FREE' AND active = TRUE",
            email,
        )
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "duplicate_key",
                    "message": "An active FREE key already exists for this email address.",
                    "status": 409,
                },
            )

        key   = _generate_raw_key()
        limit = _PLAN_LIMITS["FREE"]
        row   = await conn.fetchrow(
            """
            INSERT INTO product.api_keys (key, name, email, plan, requests_limit)
            VALUES ($1, $2, $3, 'FREE', $4)
            RETURNING id::text AS id, key, name, email, plan,
                      requests_this_month, requests_limit, active, reset_at
            """,
            key, name, email, limit,
        )

    await send_welcome_email(key=key, name=name, email=email)

    return JSONResponse(
        status_code=201,
        content={
            "key":            key,  # shown only on creation
            "plan":           "FREE",
            "requests_limit": limit,
            "message": (
                "Your FREE API key has been generated. "
                "Store it safely — it will not be shown again."
            ),
        },
    )


@router.get("/keys/me", response_model=None)
async def get_key_me(
    key_info: dict[str, Any] = Depends(get_api_key),
) -> dict:
    """Return current key metadata (plan, quota, reset date)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::text AS id, key, name, email, plan,
                   requests_this_month, requests_limit, active, reset_at
            FROM product.api_keys WHERE key = $1
            """,
            key_info["key"],
        )
    if row is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_api_key", "message": "Key not found.", "status": 401},
        )
    return _key_info_response(row)


@router.delete("/keys/me", status_code=204, response_model=None)
async def revoke_key_me(
    key_info: dict[str, Any] = Depends(get_api_key),
) -> Response:
    """Deactivate (revoke) the current key."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE product.api_keys SET active = FALSE WHERE key = $1",
            key_info["key"],
        )
    return Response(status_code=204)
