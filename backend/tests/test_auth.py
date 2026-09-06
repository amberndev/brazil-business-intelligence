"""
Tests for X-API-Key auth dependency and rate limiting (including FINDING 3 atomic counters).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from tests.conftest import make_key_row, make_mock_conn, make_mock_pool, make_test_client


def _make_client(fetchrow_return):
    """Helper: build a TestClient where pool.fetchrow returns the given row."""
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    conn = make_mock_conn(fetchrow_return=fetchrow_return)
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    ctx = patch.object(db_module, "create_pool", _inject), \
          patch.object(db_module, "close_pool", _noop)
    return ctx, conn


def test_missing_api_key(client):
    tc, _ = client
    resp = tc.get("/v1/company/11222333000181")  # valid CNPJ digits
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "missing_api_key"


def test_invalid_api_key(client):
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    conn = make_mock_conn(fetchrow_return=None)  # key not found
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get("/v1/company/11222333000181", headers={"X-API-Key": "bbi_bad"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_api_key"


def test_inactive_key(client):
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    row = make_key_row(active=False)
    conn = make_mock_conn(fetchrow_return=row)
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get("/v1/company/11222333000181", headers={"X-API-Key": row["key"]})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_api_key"


def test_plan_forbidden_compliance_on_free(client):
    """FREE plan key should get 403 on the STARTER+ compliance endpoint."""
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    row = make_key_row(plan="FREE", requests_limit=50)
    conn = make_mock_conn(fetchrow_return=row)
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get(
                "/v1/company/11222333000181/compliance",
                headers={"X-API-Key": row["key"]},
            )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "plan_forbidden"


def test_rate_limit_exceeded(client):
    """Key at quota limit (requests_this_month == requests_limit) should get 429."""
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient

    row = make_key_row(plan="FREE", requests_this_month=50, requests_limit=50)
    conn = make_mock_conn(fetchrow_return=row)
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get("/v1/company/11222333000181", headers={"X-API-Key": row["key"]})
    assert resp.status_code == 429
    body = resp.json()
    assert body["error"]["code"] == "rate_limit_exceeded"
    assert "X-RateLimit-Reset" in resp.headers


def test_ratelimit_headers_on_success():
    """Successful response must include X-RateLimit-* headers."""
    import app.db as db_module
    from app.main import app
    from fastapi.testclient import TestClient
    from datetime import date

    row = make_key_row(plan="PRO", requests_this_month=10, requests_limit=15000)

    company_row = {
        "razao_social": "EMPRESA TESTE LTDA",
        "nome_fantasia": None,
        "situacao_cadastral": "2",
        "porte_empresa": "03",
        "data_inicio_atividade": date(2020, 1, 1),
        "capital_social": 10000,
        "natureza_juridica_desc": "Sociedade Empresária Limitada",
        "cnae_fiscal_principal": "6201501",
        "cnae_principal_desc": "Desenvolvimento de programas de computador",
        "tipo_logradouro": "RUA",
        "logradouro": "DAS FLORES",
        "numero": "100",
        "complemento": None,
        "bairro": "CENTRO",
        "cep": "01310000",
        "uf": "SP",
        "municipio_desc": "SAO PAULO",
        "ddd_telefone_1": "11",
        "telefone_1": "999999999",
        "email": "empresa@teste.com",
        "cnae_secundaria_raw": "",
    }

    conn = make_mock_conn(fetchrow_return=None)
    # First fetchrow call → key lookup; second → company profile
    conn.fetchrow = AsyncMock(side_effect=[row, company_row])
    pool = make_mock_pool(conn)

    async def _inject():
        db_module._pool = pool

    async def _noop():
        db_module._pool = None

    with patch.object(db_module, "create_pool", _inject), \
         patch.object(db_module, "close_pool", _noop):
        with TestClient(app, raise_server_exceptions=False) as tc:
            resp = tc.get("/v1/company/11222333000181", headers={"X-API-Key": row["key"]})

    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers


# ── FINDING 3: atomic counter tests ───────────────────────────────────────────

def test_rate_limit_atomic_incr_on_first_request():
    """First request seeds counter at requests_this_month and INCRs to +1."""
    from datetime import date
    key = make_key_row(plan="FREE", requests_this_month=0, requests_limit=50)
    company_row = {
        "razao_social": "TEST", "nome_fantasia": None, "situacao_cadastral": "2",
        "porte_empresa": "03", "data_inicio_atividade": date(2020, 1, 1),
        "capital_social": 10000, "natureza_juridica_desc": "Ltda",
        "cnae_fiscal_principal": "6201501", "cnae_principal_desc": "Dev",
        "tipo_logradouro": "RUA", "logradouro": "X", "numero": "1",
        "complemento": None, "bairro": "Y", "cep": "01001000", "uf": "SP",
        "municipio_desc": "SAO PAULO", "ddd_telefone_1": "11",
        "telefone_1": "99999999", "email": "a@b.com", "cnae_secundaria_raw": "",
    }
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(side_effect=[key, company_row])
    with make_test_client(conn=conn) as (tc, _):
        resp = tc.get("/v1/company/11222333000181", headers={"X-API-Key": key["key"]})
    assert resp.status_code == 200
    # After 1 request from a 50-limit key starting at 0: remaining = 49
    assert resp.headers["X-RateLimit-Remaining"] == "49"


def test_rate_limit_window_reset_via_setnx():
    """After simulated window reset (cache miss), seeds from DB and counts fresh."""
    from app import cache as cache_module
    from app.cache import InMemoryCache

    fresh_cache = InMemoryCache()  # empty: simulates window reset
    key = make_key_row(plan="FREE", requests_this_month=0, requests_limit=50)

    from datetime import date
    company_row = {
        "razao_social": "TEST", "nome_fantasia": None, "situacao_cadastral": "2",
        "porte_empresa": "03", "data_inicio_atividade": date(2020, 1, 1),
        "capital_social": 10000, "natureza_juridica_desc": "Ltda",
        "cnae_fiscal_principal": "6201501", "cnae_principal_desc": "Dev",
        "tipo_logradouro": "RUA", "logradouro": "X", "numero": "1",
        "complemento": None, "bairro": "Y", "cep": "01001000", "uf": "SP",
        "municipio_desc": "SAO PAULO", "ddd_telefone_1": "11",
        "telefone_1": "99999999", "email": "a@b.com", "cnae_secundaria_raw": "",
    }
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(side_effect=[key, company_row])

    with make_test_client(conn=conn) as (tc, _):
        # Patch the module-level cache with a fresh in-memory instance
        with patch.object(cache_module, "cache", fresh_cache):
            # Need auth module to see the same fresh cache
            import app.auth as auth_module
            with patch.object(auth_module, "cache", fresh_cache):
                resp = tc.get("/v1/company/11222333000181", headers={"X-API-Key": key["key"]})
    assert resp.status_code == 200
    # After window reset, first request: remaining = 49 (50 - 1)
    assert resp.headers["X-RateLimit-Remaining"] == "49"


def test_rate_limit_fallback_in_memory():
    """Rate limit enforced via in-memory when RedisWithFallback has no Redis URL."""
    from app.cache import RedisWithFallback
    from app import cache as cache_module
    import app.auth as auth_module

    mem_cache = RedisWithFallback("")  # in-memory only
    key = make_key_row(plan="FREE", requests_this_month=49, requests_limit=50)

    from datetime import date
    company_row = {
        "razao_social": "TEST", "nome_fantasia": None, "situacao_cadastral": "2",
        "porte_empresa": "03", "data_inicio_atividade": date(2020, 1, 1),
        "capital_social": 10000, "natureza_juridica_desc": "Ltda",
        "cnae_fiscal_principal": "6201501", "cnae_principal_desc": "Dev",
        "tipo_logradouro": "RUA", "logradouro": "X", "numero": "1",
        "complemento": None, "bairro": "Y", "cep": "01001000", "uf": "SP",
        "municipio_desc": "SAO PAULO", "ddd_telefone_1": "11",
        "telefone_1": "99999999", "email": "a@b.com", "cnae_secundaria_raw": "",
    }
    conn = make_mock_conn()
    # First request succeeds (49 → 50, remaining=0), second is blocked (50 → 51 > 50)
    conn.fetchrow = AsyncMock(side_effect=[key, company_row, key])

    with make_test_client(conn=conn) as (tc, _):
        with patch.object(cache_module, "cache", mem_cache), \
             patch.object(auth_module,  "cache", mem_cache):
            r1 = tc.get("/v1/company/11222333000181", headers={"X-API-Key": key["key"]})
            r2 = tc.get("/v1/company/11222333000181", headers={"X-API-Key": key["key"]})

    assert r1.status_code == 200
    assert r1.headers["X-RateLimit-Remaining"] == "0"
    assert r2.status_code == 429
    assert r2.json()["error"]["code"] == "rate_limit_exceeded"
