from __future__ import annotations

from tests.conftest import make_mock_conn, make_mock_pool
from unittest.mock import AsyncMock, patch


def test_health_ok(client):
    tc, _ = client
    resp = tc.get("/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "memory-fallback"
    assert body["version"] == "1.0.0"


def test_health_db_error():
    """Health returns degraded when pool.acquire raises."""
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    bad_conn = make_mock_conn()
    bad_conn.fetchval = AsyncMock(side_effect=Exception("connection refused"))
    bad_pool = make_mock_pool(bad_conn)

    async def _inject():
        db_module._pool = bad_pool

    async def _noop_close():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop_close):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get("/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["db"] == "error"
