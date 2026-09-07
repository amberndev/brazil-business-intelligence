"""Regression coverage for branch navigation and search query routing."""
from unittest.mock import AsyncMock
import sqlite3

import pytest

from app.routers.search import _build_where
from tests.conftest import make_key_row, make_mock_conn, make_test_client
from tests.test_company import COMPANY_ROW


@pytest.mark.parametrize("query", ["00000000017086", "00.000.000/0170-86", " 00.000.000/0170-86 "])
def test_full_cnpj_search_uses_exact_indexed_lookup(query):
    key = make_key_row()
    conn = make_mock_conn(fetchrow_return=key, fetchval_return=1)
    with make_test_client(conn=conn) as (client, _):
        response = client.get("/v1/search", params={"q": query}, headers={"X-API-Key": key["key"]})
    assert response.status_code == 200
    sql, *params = conn.fetch.call_args.args
    assert "b.cnpj = $1" in sql
    assert "to_tsvector" not in sql
    assert params == ["00000000017086", 20, 0]
    assert conn.fetchval.call_args.args[1:] == ("00000000017086",)


@pytest.mark.parametrize("query", ["Banco do Brasil", "3M DO BRASIL", "D'AVILA"])
def test_names_keep_indexed_portuguese_fts(query):
    where, params = _build_where(query, None, None, None, None, None, None, None)
    assert "plainto_tsquery('portuguese'::regconfig, $1)" in where
    assert params == [query]
    assert query not in where


@pytest.mark.parametrize("present", [True, False])
def test_city_and_contact_filters_apply_to_both_queries(present):
    key = make_key_row()
    conn = make_mock_conn(fetchrow_return=key)
    with make_test_client(conn=conn) as (client, _):
        response = client.get("/v1/search", params={
            "city": "São Paulo", "has_email": present, "has_phone": present,
        }, headers={"X-API-Key": key["key"]})
    assert response.status_code == 200
    count_sql, *count_params = conn.fetchval.call_args.args
    data_sql, *data_params = conn.fetch.call_args.args
    assert count_params == ["Sao Paulo", present, present]
    assert data_params == count_params + [20, 0]
    for sql in (count_sql, data_sql):
        assert "b.municipio IN (SELECT codigo FROM receita.municipios" in sql
        assert "TRIM(b.email)" in sql
        assert "TRIM(b.telefone_2)" in sql
    assert "ORDER BY b.cnpj" in data_sql


def test_branch_search_result_opens_profile():
    key = make_key_row()
    conn = make_mock_conn()

    async def fetchrow(sql, *params):
        if "receita.estabelecimentos" not in sql:
            return key
        # Model the real branch: the old headquarters-only query returns no row.
        if "identificador_matriz_filial = 1" in sql:
            return None
        assert params == ("00000000", "0170", "86")
        return COMPANY_ROW

    conn.fetchrow = AsyncMock(side_effect=fetchrow)
    with make_test_client(conn=conn) as (client, _):
        response = client.get("/v1/company/00000000017086", headers={"X-API-Key": key["key"]})
    assert response.status_code == 200
    assert response.json()["data"]["cnpj"] == "00000000017086"


@pytest.mark.parametrize("email,phone,expected", [
    (True, None, ["email"]), (False, None, ["blank", "primary", "secondary"]),
    (None, True, ["primary", "secondary"]), (None, False, ["blank", "email"]),
    (False, True, ["primary", "secondary"]),
])
def test_contact_predicates_handle_null_blank_and_secondary_phone(email, phone, expected):
    # These predicates use portable SQL: execute them against real rows, so a
    # non-null whitespace value or a secondary-only phone cannot regress silently.
    where, params = _build_where(None, None, None, None, None, None, email, phone)
    with sqlite3.connect(":memory:") as conn:
        rows = conn.execute("""
            WITH b(cnpj,email,telefone,telefone_2) AS (VALUES
                ('blank', '   ', NULL, ' '),
                ('email', 'a@example.test', '', NULL),
                ('primary', NULL, '11999999999', NULL),
                ('secondary', '', ' ', '11988888888')
            ) SELECT cnpj FROM b WHERE """ + where + " ORDER BY cnpj",
            {str(i): value for i, value in enumerate(params, 1)}).fetchall()
    assert [row[0] for row in rows] == expected
