"""
GET /v1/search — filtered company search with pagination.

Plan gating:
  FREE+   — JSON results
  PRO+    — export=csv (returns text/csv attachment)

TODO(backend): verify table/column names against live schema.
TODO(backend): has_debt EXISTS subquery is slow on large tables — replace
               with a denormalized flag column or pre-computed materialized view.
"""
from __future__ import annotations

import csv
import io
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from ..auth import (
    after_usage,
    check_rate_limit,
    get_api_key,
    make_meta,
    record_usage,
    require_plan,
    set_ratelimit_headers,
    PLAN_ORDER,
)
from ..db import get_pool

router = APIRouter(tags=["search"])

# ── Enum validation ────────────────────────────────────────────────────────────

_VALID_SIZES   = {"MEI", "ME", "EPP", "MEDIO", "GRANDE"}
_VALID_STATUSES = {"ATIVA", "BAIXADA", "SUSPENSA"}

# Receita Federal porte_empresa codes (verify against live schema).
_SIZE_TO_CODE: dict[str, str] = {
    "MEI": "00",   # TODO(backend): MEI may be identified by natureza_juridica in live data
    "ME":  "01",
    "EPP": "03",
    "MEDIO": "05",
    "GRANDE": "05",  # TODO(backend): GRANDE not separately coded in Receita data
}
_STATUS_TO_CODE: dict[str, str] = {
    "ATIVA":    "2",
    "SUSPENSA": "3",
    "BAIXADA":  "8",
}
_STATUS_CODE_TO_LABEL: dict[str, str] = {"2": "ATIVA", "3": "SUSPENSA", "4": "SUSPENSA", "8": "BAIXADA"}


# ── SQL builder ────────────────────────────────────────────────────────────────

_BASE_FROM = """
FROM estabelecimentos es
JOIN empresas em ON em.cnpj_basico = es.cnpj_basico
LEFT JOIN cnaes cn ON cn.codigo = es.cnae_fiscal_principal
LEFT JOIN municipios mu ON mu.codigo = es.municipio
"""

_SELECT_COLS = """
    (es.cnpj_basico || es.cnpj_ordem || es.cnpj_dv) AS cnpj,
    COALESCE(NULLIF(TRIM(es.nome_fantasia), ''), em.razao_social) AS name,
    mu.descricao          AS city,
    es.uf                 AS state,
    cn.descricao          AS sector,
    es.situacao_cadastral AS situacao_cadastral,
    EXISTS(
        SELECT 1 FROM pgfn_divida_ativa p
        WHERE p.cnpj = (es.cnpj_basico || es.cnpj_ordem || es.cnpj_dv)
    ) AS has_debt
"""


def _build_where(
    q: Optional[str],
    state: Optional[str],
    city: Optional[str],
    sector: Optional[str],
    size_code: Optional[str],
    status_code: Optional[str],
    has_debt: Optional[bool],
    has_email: Optional[bool],
    has_phone: Optional[bool],
) -> tuple[str, list]:
    params: list = []
    conds = ["es.identificador_matriz_filial = '1'"]

    def p(val: Any) -> str:
        params.append(val)
        return f"${len(params)}"

    if q:
        ref = p(q)
        conds.append(
            f"(em.razao_social ILIKE '%%' || {ref} || '%%'"
            f" OR es.nome_fantasia ILIKE '%%' || {ref} || '%%')"
        )
    if state:
        conds.append(f"es.uf = {p(state.upper())}")
    if city:
        conds.append(f"mu.descricao ILIKE '%%' || {p(city)} || '%%'")
    if sector:
        ref = p(sector)
        conds.append(f"(es.cnae_fiscal_principal = {ref} OR cn.descricao ILIKE '%%' || {ref} || '%%')")
    if size_code:
        conds.append(f"em.porte_empresa = {p(size_code)}")
    if status_code:
        conds.append(f"es.situacao_cadastral = {p(status_code)}")
    if has_email:
        conds.append("(es.email IS NOT NULL AND es.email <> '')")
    if has_phone:
        conds.append("(es.ddd_telefone_1 IS NOT NULL AND es.ddd_telefone_1 <> '')")
    if has_debt:
        conds.append(
            "EXISTS(SELECT 1 FROM pgfn_divida_ativa p"
            " WHERE p.cnpj = (es.cnpj_basico || es.cnpj_ordem || es.cnpj_dv))"
        )

    return " AND ".join(conds), params


def _row_to_result(r: Any) -> dict:
    cnpj = str(r["cnpj"]) if r["cnpj"] else ""
    return {
        "cnpj": cnpj,
        "cnpj_formatted": (
            f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
            if len(cnpj) == 14 else cnpj
        ),
        "name": str(r["name"]) if r["name"] else "",
        "city": str(r["city"]) if r["city"] else None,
        "state": str(r["state"]) if r["state"] else None,
        "sector": str(r["sector"]) if r["sector"] else None,
        "status": _STATUS_CODE_TO_LABEL.get(str(r["situacao_cadastral"]).strip(), "BAIXADA"),
        "has_debt": bool(r["has_debt"]),
    }


# ── Route ──────────────────────────────────────────────────────────────────────

@router.get("/search", response_model=None)
async def get_search(
    response: Response,
    q:         Optional[str]  = Query(None),
    state:     Optional[str]  = Query(None),
    city:      Optional[str]  = Query(None),
    sector:    Optional[str]  = Query(None),
    size:      Optional[str]  = Query(None),
    status:    Optional[str]  = Query(None),
    has_debt:  Optional[bool] = Query(None),
    has_email: Optional[bool] = Query(None),
    has_phone: Optional[bool] = Query(None),
    page:      int            = Query(1, ge=1),
    limit:     int            = Query(20, ge=1),
    export:    Optional[str]  = Query(None),
    key_info: dict[str, Any] = Depends(get_api_key),
) -> Any:
    # ── enum validation ──
    if size and size not in _VALID_SIZES:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_filter", "message": f"Invalid size value '{size}'. Valid: {', '.join(sorted(_VALID_SIZES))}.", "status": 422},
        )
    if status and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_filter", "message": f"Invalid status value '{status}'. Valid: {', '.join(sorted(_VALID_STATUSES))}.", "status": 422},
        )

    # ── export=csv requires PRO+ ──
    if export == "csv":
        plan = key_info.get("plan", "FREE")
        if PLAN_ORDER.get(plan, 0) < PLAN_ORDER.get("PRO", 2):
            raise HTTPException(
                status_code=403,
                detail={"code": "plan_forbidden", "message": "CSV export requires the PRO plan or higher.", "status": 403},
            )

    requests_remaining = await check_rate_limit(key_info)

    limit = min(limit, 100)
    offset = (page - 1) * limit
    size_code   = _SIZE_TO_CODE.get(size)   if size   else None
    status_code = _STATUS_TO_CODE.get(status) if status else None

    where, params = _build_where(q, state, city, sector, size_code, status_code, has_debt, has_email, has_phone)

    count_sql = f"SELECT COUNT(*) {_BASE_FROM} WHERE {where}"
    data_sql = (
        f"SELECT {_SELECT_COLS} {_BASE_FROM} WHERE {where}"
        f" ORDER BY em.razao_social"
        f" LIMIT ${len(params)+1} OFFSET ${len(params)+2}"
    )
    data_params = params + [limit, offset]

    t0 = time.perf_counter()
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(count_sql, *params)
        rows  = await conn.fetch(data_sql, *data_params)
    query_time_ms = (time.perf_counter() - t0) * 1000

    total = int(total or 0)
    results = [_row_to_result(r) for r in rows]
    total_pages = max(1, (total + limit - 1) // limit)

    await record_usage(key_info)
    set_ratelimit_headers(response, key_info, after_usage(requests_remaining))

    if export == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["cnpj", "cnpj_formatted", "name", "city", "state", "sector", "status", "has_debt"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(results)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=\"companies.csv\""},
        )

    return {
        "data": {
            "results": results,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            },
        },
        "meta": make_meta(key_info, after_usage(requests_remaining), query_time_ms),
    }
