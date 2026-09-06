"""Tests for GET /v1/market/overview (PRO+)."""
from __future__ import annotations

from unittest.mock import AsyncMock

from tests.conftest import make_key_row, make_mock_conn, make_test_client

_PRO_KEY     = make_key_row(plan="PRO",     requests_limit=15000)
_FREE_KEY    = make_key_row(plan="FREE",    requests_limit=50)
_STARTER_KEY = make_key_row(plan="STARTER", requests_limit=2000)
_ENT_KEY     = make_key_row(plan="ENTERPRISE", requests_limit=-1)

_STATE_ROWS  = [{"state": "SP", "count": 5000000}, {"state": "RJ", "count": 2000000}]
_SECTOR_ROWS = [{"cnae": "6201501", "description": "Dev software", "count": 120000}]


def _make(key_row, state_rows=None, sector_rows=None):
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(return_value=key_row)
    conn.fetch    = AsyncMock(side_effect=[
        state_rows  if state_rows  is not None else _STATE_ROWS,
        sector_rows if sector_rows is not None else _SECTOR_ROWS,
    ])
    return make_test_client(conn=conn)


def test_market_overview_pro():
    with _make(_PRO_KEY) as (tc, _):
        resp = tc.get("/v1/market/overview", headers={"X-API-Key": _PRO_KEY["key"]})
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body and "meta" in body
    data = body["data"]
    assert data["total_companies"] == 7000000  # sum of state rows
    assert len(data["by_state"]) == 2
    assert data["by_state"][0]["state"] == "SP"
    assert len(data["by_sector"]) == 1
    assert data["by_sector"][0]["cnae"] == "6201501"
    assert data["by_sector"][0]["description"] == "Dev software"


def test_market_overview_enterprise():
    with _make(_ENT_KEY) as (tc, _):
        resp = tc.get("/v1/market/overview", headers={"X-API-Key": _ENT_KEY["key"]})
    assert resp.status_code == 200
    meta = resp.json()["meta"]
    assert meta["requests_remaining"] == -1
    assert meta["plan"] == "ENTERPRISE"


def test_market_overview_free_forbidden():
    with _make(_FREE_KEY) as (tc, _):
        resp = tc.get("/v1/market/overview", headers={"X-API-Key": _FREE_KEY["key"]})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "plan_forbidden"


def test_market_overview_starter_forbidden():
    with _make(_STARTER_KEY) as (tc, _):
        resp = tc.get("/v1/market/overview", headers={"X-API-Key": _STARTER_KEY["key"]})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "plan_forbidden"


def test_market_overview_empty_db():
    with _make(_PRO_KEY, state_rows=[], sector_rows=[]) as (tc, _):
        resp = tc.get("/v1/market/overview", headers={"X-API-Key": _PRO_KEY["key"]})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_companies"] == 0
    assert data["by_state"] == []
    assert data["by_sector"] == []
