"""
Test fixtures.

Strategy:
- Patch app.db.create_pool / close_pool to no-ops so the lifespan never
  opens a real Postgres connection.
- Inject a MagicMock pool via app.db._pool so get_pool() succeeds.
- Use TestClient against the FastAPI app.
- In-memory cache (app.cache.cache) is used as-is — no Redis needed.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient


# ── Shared data helpers ───────────────────────────────────────────────────────

def make_key_row(
    *,
    plan: str = "PRO",
    active: bool = True,
    requests_this_month: int = 5,
    requests_limit: int = 15000,
    key: str | None = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "key": key or ("bbi_test_" + uuid.uuid4().hex[:28]),
        "plan": plan,
        "active": active,
        "requests_this_month": requests_this_month,
        "requests_limit": requests_limit,
        "reset_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "name": "Test User",
        "email": "test@example.com",
    }


def make_mock_conn(
    fetchrow_return: Any = None,
    fetchval_return: Any = 1,
    fetch_return: Any = None,
) -> MagicMock:
    conn = AsyncMock()
    conn.fetchrow   = AsyncMock(return_value=fetchrow_return)
    conn.fetchval   = AsyncMock(return_value=fetchval_return)
    conn.fetch      = AsyncMock(return_value=fetch_return or [])
    conn.execute    = AsyncMock(return_value=None)
    return conn


def make_mock_pool(conn: MagicMock) -> MagicMock:
    pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__  = AsyncMock(return_value=False)
    pool.acquire  = MagicMock(return_value=cm)
    pool.fetchval = conn.fetchval
    return pool


@contextmanager
def make_test_client(conn: MagicMock | None = None, pool: MagicMock | None = None):
    """
    Context manager that yields (TestClient, conn).
    Pass a pre-configured conn/pool or let it create defaults.
    """
    import app.db as db_module

    if conn is None:
        conn = make_mock_conn()
    if pool is None:
        pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc, conn


# ── Pytest fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_conn() -> MagicMock:
    return make_mock_conn()


@pytest.fixture
def mock_pool(mock_conn: MagicMock) -> MagicMock:
    return make_mock_pool(mock_conn)


@pytest.fixture
def client(mock_pool: MagicMock):
    """TestClient with DB pool stubbed out. Yields (TestClient, mock_pool)."""
    import app.db as db_module

    async def _noop_create():
        db_module._pool = mock_pool

    async def _noop_close():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _noop_create), \
         patch.object(db_module, "close_pool", _noop_close):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c, mock_pool
