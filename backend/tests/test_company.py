"""
Tests for GET /v1/company/{cnpj} and GET /v1/company/{cnpj}/compliance.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

from tests.conftest import make_key_row, make_mock_conn, make_mock_pool

_VALID_CNPJ = "11222333000181"  # passes check-digit validation
_INVALID_CNPJ = "00000000000000"
_MASKED_CNPJ = "11.222.333/0001-81"
_MASKED_CNPJ_ENCODED = "11.222.333%2F0001-81"  # URL-safe: / → %2F for path param

KEY_ROW = make_key_row(plan="PRO", requests_this_month=0, requests_limit=15000)

COMPANY_ROW = {
    "razao_social": "EMPRESA DEMO LTDA",
    "nome_fantasia": "DEMO CO",
    "situacao_cadastral": 2,
    "porte": 3,
    "data_inicio_atividade": date(2015, 6, 10),
    "capital_social": 50000,
    "natureza_juridica_desc": "Sociedade Empresária Limitada",
    "cnae_fiscal_principal": "6201501",
    "cnae_principal_desc": "Desenvolvimento de programas de computador sob encomenda",
    "tipo_logradouro": "RUA",
    "logradouro": "JOSE ANTONIO",
    "numero": "55",
    "complemento": "SALA 3",
    "bairro": "CENTRO",
    "cep": "04560000",
    "uf": "SP",
    "municipio_desc": "SAO PAULO",
    "ddd1": "11",
    "telefone1": "988887777",
    "correio_eletronico": "contato@demo.com",
    "cnae_secundaria_raw": "6202300,6209100",
}


def _make_client_with_side_effect(side_effect):
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(side_effect=side_effect)
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    return (
        patch.object(db_module, "create_pool", _inject),
        patch.object(db_module, "close_pool", _noop),
        app,
        conn,
    )


# ── CNPJ validation tests ──────────────────────────────────────────────────────

def test_invalid_cnpj_format(client):
    tc, _ = client
    resp = tc.get("/v1/company/1234", headers={"X-API-Key": KEY_ROW["key"]})
    # auth will fail first (pool returns None for this key in default fixture)
    # just ensure we don't crash with 500
    assert resp.status_code in (401, 422)


def test_invalid_cnpj_check_digit():
    """CNPJ with wrong check digits returns 422 invalid_cnpj."""
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    conn = make_mock_conn(fetchrow_return=KEY_ROW)
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get("/v1/company/12345678000100", headers={"X-API-Key": KEY_ROW["key"]})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_cnpj"


def test_masked_cnpj_normalization():
    """
    normalize_cnpj strips mask and validates check digits.
    The '/' in the mask is not URL-path-safe, so clients send raw digits in the
    URL and include the mask only as display; we test the normalizer directly.
    """
    from app.routers.company import normalize_cnpj, format_cnpj

    normalized = normalize_cnpj(_MASKED_CNPJ)
    assert normalized == _VALID_CNPJ

    assert normalize_cnpj(_VALID_CNPJ) == _VALID_CNPJ
    assert format_cnpj(_VALID_CNPJ) == _MASKED_CNPJ


# ── Company profile endpoint ──────────────────────────────────────────────────

def test_company_profile_success():
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(side_effect=[KEY_ROW, COMPANY_ROW])
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get(f"/v1/company/{_VALID_CNPJ}", headers={"X-API-Key": KEY_ROW["key"]})

    assert resp.status_code == 200
    body = resp.json()

    # Envelope shape
    assert "data" in body
    assert "meta" in body
    assert "query_time_ms" in body["meta"]
    assert "plan" in body["meta"]
    assert "requests_remaining" in body["meta"]
    assert body["meta"]["plan"] == "PRO"

    data = body["data"]
    # Contract field names verbatim
    assert data["cnpj"] == _VALID_CNPJ
    assert data["cnpj_formatted"] == _MASKED_CNPJ
    assert data["razao_social"] == "EMPRESA DEMO LTDA"
    assert data["nome_fantasia"] == "DEMO CO"
    assert data["status"] == "ATIVA"
    assert data["size"] == "EPP"
    assert data["opened_at"] == "2015-06-10"
    assert data["legal_nature"] == "Sociedade Empresária Limitada"
    assert data["share_capital"] == 50000.0
    assert data["location"]["state"] == "SP"
    assert data["location"]["city"] == "SAO PAULO"
    assert data["sector"]["primary_cnae"]["code"] == "6201501"
    assert len(data["sector"]["secondary_cnae"]) == 2
    assert data["contact"]["phone"] == "+5511988887777"
    assert data["contact"]["email"] == "contato@demo.com"


def test_company_profile_not_found():
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(side_effect=[KEY_ROW, None])  # company not found
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get(f"/v1/company/{_VALID_CNPJ}", headers={"X-API-Key": KEY_ROW["key"]})

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


# ── Compliance endpoint ───────────────────────────────────────────────────────

def test_compliance_success():
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    pgfn_row = {"records_count": 2, "total_amount": 150000.00}

    from datetime import date as dt
    cgu_rows = [
        {
            "type": "CEIS",
            "description": "Irregularidade X",
            "start_date": dt(2022, 1, 1),
            "end_date": dt(2023, 12, 31),
        }
    ]

    conn = make_mock_conn()
    # auth fetchrow → KEY_ROW; PGFN fetchrow → pgfn_row
    # exists check uses fetchval (separate mock), NOT fetchrow
    conn.fetchrow = AsyncMock(side_effect=[KEY_ROW, pgfn_row])
    conn.fetchval = AsyncMock(return_value=1)  # company exists
    conn.fetch = AsyncMock(return_value=cgu_rows)
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get(
                f"/v1/company/{_VALID_CNPJ}/compliance",
                headers={"X-API-Key": KEY_ROW["key"]},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    data = body["data"]
    assert data["cnpj"] == _VALID_CNPJ
    assert "pgfn_debt" in data
    assert "cgu_sanctions" in data
    pgfn = data["pgfn_debt"]
    assert pgfn["has_debt"] is True
    assert pgfn["records_count"] == 2
    assert pgfn["total_amount"] == 150000.00
    cgu = data["cgu_sanctions"]
    assert cgu["has_sanctions"] is True
    assert cgu["count"] == 1
    assert cgu["items"][0]["type"] == "CEIS"
    assert cgu["items"][0]["start_date"] == "2022-01-01"


def test_compliance_free_plan_forbidden():
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    free_row = make_key_row(plan="FREE", requests_limit=50)
    conn = make_mock_conn(fetchrow_return=free_row)
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get(
                f"/v1/company/{_VALID_CNPJ}/compliance",
                headers={"X-API-Key": free_row["key"]},
            )

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "plan_forbidden"


def test_compliance_not_found():
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(return_value=KEY_ROW)
    conn.fetchval = AsyncMock(return_value=None)  # company not found
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get(
                f"/v1/company/{_VALID_CNPJ}/compliance",
                headers={"X-API-Key": KEY_ROW["key"]},
            )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
