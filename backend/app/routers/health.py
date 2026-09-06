from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..cache import cache
from ..db import get_pool

router = APIRouter(tags=["health"])

VERSION = "1.0.0"


@router.get("/health", response_model=None)
async def health() -> JSONResponse:
    db_status = "ok"
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        db_status = "error"

    if cache._redis is not None:
        try:
            await cache._redis.ping()
            redis_status = "ok"
        except Exception:
            redis_status = "error"
    else:
        redis_status = "memory-fallback"

    overall = "ok" if db_status == "ok" else "degraded"

    return JSONResponse(
        status_code=200,
        content={
            "status": overall,
            "db": db_status,
            "redis": redis_status,
            "version": VERSION,
        },
    )
