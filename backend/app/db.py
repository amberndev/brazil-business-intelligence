from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from fastapi import FastAPI

from .config import settings

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — lifespan did not run")
    return _pool


async def create_pool() -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_pool()
    from .cache import cache  # late import — avoid circular at module level
    await cache.startup()
    yield
    await close_pool()
