"""Tests for GET /v1/company/{cnpj}/shareholders (STARTER+)."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

from tests.conftest import make_key_row, make_mock_conn, make_test_client

_CNPJ = "11222333000181"

_STARTER_KEY = make_key_row(plan="STARTER")
_FREE_KEY    = make_key_row(plan="FREE",    requests_limit=50)
_PRO_KEY     = make_key_row(plan="PRO",     requests_limit=15000)

_SHAREHOLDER_ROWS = [
    {
        "name":         "JOAO SILVA",
        "document_raw": "12345678901",  # CPF
        "role":         "Sócio-Administrador",
        "since_raw":    date(2015, 6, 10),
    },
    {
        "name":         "MARIA OLIVEIRA",
        "document_raw": "98765432100",  # CPF
        "role":         "Sócio",
        "since_raw":    None,
    },
]


def _make(key_row, fetchval_return=1, fetch_return=None):
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(return_value=key_row)
    conn.fetchval = AsyncMock(return_value=fetchval_return)
    conn.fetch    = AsyncMock(return_value=fetch_return or _SHAREHOLDER_ROWS)
    return make_test_client(conn=conn)


def test_shareholders_success():
    with _make(_STARTER_KEY) as (tc, _):
        resp = tc.get(f"/v1/company/{_CNPJ}/shareholders", headers={"X-API-Key": _STARTER_KEY["key"]})
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body and "meta" in body
    data = body["data"]
    assert data["cnpj"] == _CNPJ
    assert data["count"] == 2
    sh = data["shareholders"]
    assert sh[0]["name"] == "JOAO SILVA"
    assert sh[0]["role"] == "Sócio-Administrador"
    assert sh[0]["since"] == "2015-06-10"
    # CPF must be masked — never expose full digits
    doc = sh[0]["document"]
    assert doc is not None
    assert "12345678" not in str(doc)  # first 8 digits must not appear
    assert sh[1]["since"] is None


def test_shareholders_free_forbidden():
    with _make(_FREE_KEY) as (tc, _):
        resp = tc.get(f"/v1/company/{_CNPJ}/shareholders", headers={"X-API-Key": _FREE_KEY["key"]})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "plan_forbidden"


def test_shareholders_not_found():
    with _make(_STARTER_KEY, fetchval_return=None, fetch_return=[]) as (tc, _):
        resp = tc.get(f"/v1/company/{_CNPJ}/shareholders", headers={"X-API-Key": _STARTER_KEY["key"]})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_shareholders_invalid_cnpj():
    with _make(_STARTER_KEY) as (tc, _):
        resp = tc.get("/v1/company/12345678000100/shareholders", headers={"X-API-Key": _STARTER_KEY["key"]})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_cnpj"


def test_shareholders_corporate_partner_cnpj_not_masked():
    """Corporate partner CNPJ (14 digits) is passed through formatted, not blanked."""
    row_with_cnpj = [
        {
            "name":         "HOLDING SA",
            "document_raw": "11222333000181",  # CNPJ of corporate partner
            "role":         "Sócio",
            "since_raw":    None,
        }
    ]
    with _make(_PRO_KEY, fetch_return=row_with_cnpj) as (tc, _):
        resp = tc.get(f"/v1/company/{_CNPJ}/shareholders", headers={"X-API-Key": _PRO_KEY["key"]})
    assert resp.status_code == 200
    doc = resp.json()["data"]["shareholders"][0]["document"]
    assert doc == "11.222.333/0001-81"
