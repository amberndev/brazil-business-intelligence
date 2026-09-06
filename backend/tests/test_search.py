"""Tests for GET /v1/search (FREE+, PRO+ for CSV export)."""
from __future__ import annotations

from unittest.mock import AsyncMock

from tests.conftest import make_key_row, make_mock_conn, make_test_client

_FREE_KEY    = make_key_row(plan="FREE",    requests_limit=50)
_PRO_KEY     = make_key_row(plan="PRO",     requests_limit=15000)
_STARTER_KEY = make_key_row(plan="STARTER", requests_limit=2000)

_SEARCH_ROW = {
    "cnpj":              "11222333000181",
    "name":              "EMPRESA DEMO LTDA",
    "city":              "SAO PAULO",
    "state":             "SP",
    "sector":            "Dev software",
    "situacao_cadastral": "2",
    "has_debt":          False,
}


def _make(key_row, total=1, rows=None):
    conn = make_mock_conn()
    rows = rows if rows is not None else [_SEARCH_ROW]
    conn.fetchrow = AsyncMock(return_value=key_row)
    conn.fetchval = AsyncMock(return_value=total)
    conn.fetch    = AsyncMock(return_value=rows)
    return make_test_client(conn=conn)


def test_search_success_free():
    with _make(_FREE_KEY) as (tc, _):
        resp = tc.get("/v1/search", headers={"X-API-Key": _FREE_KEY["key"]})
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body and "meta" in body
    data = body["data"]
    assert "results" in data and "pagination" in data
    assert data["pagination"]["total"] == 1
    assert data["pagination"]["page"] == 1
    assert len(data["results"]) == 1
    row = data["results"][0]
    assert row["cnpj"] == "11222333000181"
    assert row["status"] == "ATIVA"
    assert row["has_debt"] is False


def test_search_pagination():
    with _make(_FREE_KEY, total=100) as (tc, _):
        resp = tc.get("/v1/search?page=3&limit=10", headers={"X-API-Key": _FREE_KEY["key"]})
    assert resp.status_code == 200
    pag = resp.json()["data"]["pagination"]
    assert pag["page"] == 3
    assert pag["limit"] == 10
    assert pag["total"] == 100
    assert pag["total_pages"] == 10


def test_search_limit_clamped_to_100():
    with _make(_FREE_KEY, total=200) as (tc, _):
        resp = tc.get("/v1/search?limit=9999", headers={"X-API-Key": _FREE_KEY["key"]})
    assert resp.status_code == 200
    assert resp.json()["data"]["pagination"]["limit"] == 100


def test_search_invalid_size_filter():
    with _make(_FREE_KEY) as (tc, _):
        resp = tc.get("/v1/search?size=GIANT", headers={"X-API-Key": _FREE_KEY["key"]})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_filter"


def test_search_invalid_status_filter():
    with _make(_FREE_KEY) as (tc, _):
        resp = tc.get("/v1/search?status=ACTIVE", headers={"X-API-Key": _FREE_KEY["key"]})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_filter"


def test_search_export_csv_pro():
    with _make(_PRO_KEY) as (tc, _):
        resp = tc.get("/v1/search?export=csv", headers={"X-API-Key": _PRO_KEY["key"]})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    # CSV should contain header + 1 data row
    lines = resp.text.strip().splitlines()
    assert lines[0].startswith("cnpj")
    assert len(lines) == 2


def test_search_export_csv_free_forbidden():
    with _make(_FREE_KEY) as (tc, _):
        resp = tc.get("/v1/search?export=csv", headers={"X-API-Key": _FREE_KEY["key"]})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "plan_forbidden"


def test_search_export_csv_starter_forbidden():
    with _make(_STARTER_KEY) as (tc, _):
        resp = tc.get("/v1/search?export=csv", headers={"X-API-Key": _STARTER_KEY["key"]})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "plan_forbidden"


def test_search_missing_api_key():
    with _make(_FREE_KEY) as (tc, _):
        resp = tc.get("/v1/search")
    assert resp.status_code == 401
