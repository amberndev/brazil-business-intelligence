"""
GET /v1/market/overview — aggregate totals by state & sector.

Plan gate: PRO+ (FREE/STARTER → 403 plan_forbidden).
TODO(backend): verify table/column names against live schema.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Response

from ..auth import (
    after_usage,
    check_rate_limit,
    make_meta,
    record_usage,
    require_plan,
    set_ratelimit_headers,
)
from ..db import get_pool

router = APIRouter(tags=["market"])

_BY_STATE_SQL = """
SELECT
    es.uf    AS state,
    COUNT(*) AS count
FROM estabelecimentos es
WHERE es.identificador_matriz_filial = '1'
  {state_filter}
GROUP BY es.uf
ORDER BY count DESC
"""

_BY_SECTOR_SQL = """
SELECT
    cn.codigo    AS cnae,
    cn.descricao AS description,
    COUNT(*)     AS count
FROM estabelecimentos es
LEFT JOIN cnaes cn ON cn.codigo = es.cnae_fiscal_principal
WHERE es.identificador_matriz_filial = '1'
  {sector_filter}
GROUP BY cn.codigo, cn.descricao
ORDER BY count DESC
LIMIT 50
"""


@router.get("/market/overview", response_model=None)
async def get_market_overview(
    response: Response,
    state:  Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    key_info: dict[str, Any] = Depends(require_plan("PRO")),
) -> dict:
    requests_remaining = await check_rate_limit(key_info)

    state_params:  list = []
    sector_params: list = []

    state_filter  = ""
    sector_filter = ""

    if state:
        state_params.append(state.upper())
        state_filter = "AND es.uf = $1"

    if sector:
        sector_params.append(sector)
        sector_filter = "AND (cn.codigo = $1 OR cn.descricao ILIKE '%' || $1 || '%')"

    by_state_sql  = _BY_STATE_SQL.format(state_filter=state_filter)
    by_sector_sql = _BY_SECTOR_SQL.format(sector_filter=sector_filter)

    t0 = time.perf_counter()
    pool = await get_pool()
    async with pool.acquire() as conn:
        by_state_rows  = await conn.fetch(by_state_sql,  *state_params)
        by_sector_rows = await conn.fetch(by_sector_sql, *sector_params)
    query_time_ms = (time.perf_counter() - t0) * 1000

    total = sum(int(r["count"]) for r in by_state_rows)

    await record_usage(key_info)
    remaining = after_usage(requests_remaining)
    set_ratelimit_headers(response, key_info, remaining)

    return {
        "data": {
            "total_companies": total,
            "by_state":  [{"state": r["state"],  "count": int(r["count"])} for r in by_state_rows],
            "by_sector": [
                {"cnae": r["cnae"], "description": r["description"], "count": int(r["count"])}
                for r in by_sector_rows
            ],
        },
        "meta": make_meta(key_info, remaining, query_time_ms),
    }
