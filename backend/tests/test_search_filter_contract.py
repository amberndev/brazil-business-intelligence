"""Search must never silently ignore a requested filter or invent debt data."""
import csv
import io
import sqlite3

import pytest

from app.routers.search import _build_where
from tests.conftest import make_key_row, make_mock_conn, make_test_client
from tests.test_search import _SEARCH_ROW


@pytest.mark.parametrize("status", ["BAIXADA", "SUSPENSA", ""])
def test_unsupported_status_rejected_before_search_queries(status):
    key = make_key_row()
    conn = make_mock_conn(fetchrow_return=key)
    with make_test_client(conn=conn) as (client, _):
        result = client.get('/v1/search', params={'status': status}, headers={'X-API-Key': key['key']})
    assert result.status_code == 422
    assert result.json()['error']['code'] == 'unsupported_filter'
    conn.fetch.assert_not_awaited()
    conn.fetchval.assert_not_awaited()


@pytest.mark.parametrize("debt,expected", [(True, ['yes']), (False, ['no']), (None, ['no', 'unknown', 'yes'])])
def test_debt_predicate_executes_three_valued_logic(debt, expected):
    where, params = _build_where(None, None, None, None, None, debt, None, None)
    with sqlite3.connect(':memory:') as conn:
        rows = conn.execute("WITH b(cnpj,tem_divida) AS (VALUES ('yes',TRUE),('no',FALSE),('unknown',NULL)) SELECT cnpj FROM b WHERE " + where + " ORDER BY cnpj", params).fetchall()
    assert [row[0] for row in rows] == expected


@pytest.mark.parametrize("debt", [True, False])
def test_debt_and_active_filters_reach_count_data_and_csv(debt):
    key = make_key_row(plan='PRO')
    conn = make_mock_conn(fetchrow_return=key, fetch_return=[{**_SEARCH_ROW, 'has_debt': debt}])
    with make_test_client(conn=conn) as (client, _):
        result = client.get('/v1/search', params={'status': 'ATIVA', 'has_debt': debt, 'export': 'csv'}, headers={'X-API-Key': key['key']})
    assert result.status_code == 200
    for sql in (conn.fetchval.call_args.args[0], conn.fetch.call_args.args[0]):
        assert ('b.tem_divida = TRUE' if debt else 'b.tem_divida = FALSE') in sql
        assert 'estabelecimentos' not in sql
    row = next(csv.DictReader(io.StringIO(result.text)))
    assert row['status'] == 'ATIVA'
    assert row['has_debt'] == str(debt)


@pytest.mark.parametrize("export", [None, 'csv'])
def test_unknown_debt_preserved_in_results(export):
    key = make_key_row(plan='PRO')
    conn = make_mock_conn(fetchrow_return=key, fetch_return=[{**_SEARCH_ROW, 'has_debt': None}])
    with make_test_client(conn=conn) as (client, _):
        result = client.get('/v1/search', params={'export': export} if export else {}, headers={'X-API-Key': key['key']})
    assert result.status_code == 200
    if export:
        assert next(csv.DictReader(io.StringIO(result.text)))['has_debt'] == ''
    else:
        assert result.json()['data']['results'][0]['has_debt'] is None
