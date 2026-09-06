"""Tests for POST /v1/company/batch (STARTER+, max 50)."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

from tests.conftest import make_key_row, make_mock_conn, make_test_client

_CNPJ_A = "11222333000181"
_CNPJ_B = "11444777000161"

_STARTER_KEY = make_key_row(plan="STARTER")
_FREE_KEY    = make_key_row(plan="FREE", requests_limit=50)

_COMPANY_ROW = {
    "razao_social": "EMPRESA DEMO LTDA",
    "nome_fantasia": "DEMO CO",
    "situacao_cadastral": "2",
    "porte_empresa": "03",
    "data_inicio_atividade": date(2015, 6, 10),
    "capital_social": 50000,
    "natureza_juridica_desc": "Soc. Emp. Limitada",
    "cnae_fiscal_principal": "6201501",
    "cnae_principal_desc": "Dev software",
    "tipo_logradouro": "RUA",
    "logradouro": "TESTE",
    "numero": "1",
    "complemento": None,
    "bairro": "CENTRO",
    "cep": "01001000",
    "uf": "SP",
    "municipio_desc": "SAO PAULO",
    "ddd_telefone_1": "11",
    "telefone_1": "999999999",
    "email": "a@b.com",
    "cnae_secundaria_raw": "",
}


def _make_batch_conn(key_row, company_row_or_none):
    """fetchrow: first call = key auth; subsequent = company query per CNPJ."""
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(side_effect=[key_row, company_row_or_none])
    return conn


def test_batch_success_two_found():
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(side_effect=[_STARTER_KEY, _COMPANY_ROW, _COMPANY_ROW])
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.post(
            "/v1/company/batch",
            json={"cnpjs": [_CNPJ_A, _CNPJ_B]},
            headers={"X-API-Key": _STARTER_KEY["key"]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["count"] == 2
    for item in body["data"]["results"]:
        assert item["profile"] is not None
        assert item["error"] is None


def test_batch_empty_body():
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(return_value=_STARTER_KEY)
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.post(
            "/v1/company/batch",
            json={"cnpjs": []},
            headers={"X-API-Key": _STARTER_KEY["key"]},
        )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "batch_empty"


def test_batch_too_large():
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(return_value=_STARTER_KEY)
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.post(
            "/v1/company/batch",
            json={"cnpjs": [_CNPJ_A] * 51},
            headers={"X-API-Key": _STARTER_KEY["key"]},
        )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "batch_too_large"


def test_batch_mixed_valid_invalid():
    """Invalid CNPJ and not-found CNPJ return error items, not a whole-batch failure."""
    conn = make_mock_conn()
    # key auth + one valid company + one not found (None)
    conn.fetchrow = AsyncMock(side_effect=[_STARTER_KEY, _COMPANY_ROW, None])
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.post(
            "/v1/company/batch",
            json={"cnpjs": [_CNPJ_A, _CNPJ_B, "00000000000000"]},  # last is invalid
            headers={"X-API-Key": _STARTER_KEY["key"]},
        )
    assert resp.status_code == 200
    results = resp.json()["data"]["results"]
    assert results[0]["profile"] is not None   # found
    assert results[1]["profile"] is None        # not found
    assert results[1]["error"]["code"] == "not_found"
    assert results[2]["profile"] is None        # invalid CNPJ
    assert results[2]["error"]["code"] == "invalid_cnpj"


def test_batch_free_forbidden():
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(return_value=_FREE_KEY)
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.post(
            "/v1/company/batch",
            json={"cnpjs": [_CNPJ_A]},
            headers={"X-API-Key": _FREE_KEY["key"]},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "plan_forbidden"


def test_batch_counts_as_one_request():
    """Batch of N CNPJs counts as 1 rate-limit increment (meta.requests_remaining decreases by 1)."""
    key = make_key_row(plan="STARTER", requests_this_month=0, requests_limit=2000)
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(side_effect=[key, _COMPANY_ROW, _COMPANY_ROW])
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.post(
            "/v1/company/batch",
            json={"cnpjs": [_CNPJ_A, _CNPJ_B]},
            headers={"X-API-Key": key["key"]},
        )
    assert resp.status_code == 200
    meta = resp.json()["meta"]
    assert meta["requests_remaining"] == 1999  # 2000 - 1 (not -2)
