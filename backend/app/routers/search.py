"""
GET /v1/search — filtered company search with pagination.

Plan gating:
  FREE+   — JSON results
  PRO+    — export=csv (returns text/csv attachment)

Uses receita.busca (pre-denormalized, fully indexed) to avoid seq-scans on
the 72M-row estabelecimentos table.  Text search hits busca_nome_fts (GIN,
Portuguese FTS); uf/cnae/porte filters hit busca_nicho_uf / busca_nicho_cidade.
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

# porte is stored as smallint in receita.busca / receita.empresas
# MEI is identified by the is_mei boolean flag, not porte
_SIZE_TO_PORTE: dict[str, int | None] = {
    "MEI":   None,  # use is_mei = TRUE
    "ME":    1,
    "EPP":   3,
    "MEDIO": 5,
    "GRANDE": 5,    # RF data doesn't distinguish GRANDE from MEDIO
}


def _build_where(
    q: Optional[str],
    state: Optional[str],
    city: Optional[str],
    sector: Optional[str],
    size: Optional[str],
    has_debt: Optional[bool],
    has_email: Optional[bool],
    has_phone: Optional[bool],
) -> tuple[str, list]:
    params: list = []
    conds: list[str] = []

    def p(val: Any) -> str:
        params.append(val)
        return f"${len(params)}"

    if q:
        ref = p(q)
        conds.append(
            f"to_tsvector('portuguese'::regconfig,"
            f" COALESCE(b.nome,'')||' '||COALESCE(b.razao_social,''))"
            f" @@ plainto_tsquery('portuguese'::regconfig, {ref})"
        )
    if state:
        conds.append(f"b.uf = {p(state.upper())}")
    if city:
        conds.append(f"b.municipio_nome ILIKE '%%' || {p(city)} || '%%'")
    if sector:
        # sector may be a CNAE code (integer string) or a text description
        ref = p(sector)
        conds.append(f"(b.cnae::text = {ref} OR b.cnae_descricao ILIKE '%%' || {ref} || '%%')")
    if size == "MEI":
        conds.append("b.is_mei = TRUE")
    elif size in _SIZE_TO_PORTE and _SIZE_TO_PORTE[size] is not None:
        conds.append(f"b.porte = {p(_SIZE_TO_PORTE[size])}")
    if has_email is True:
        conds.append("(b.email IS NOT NULL AND b.email <> '')")
    if has_phone is True:
        conds.append("(b.telefone IS NOT NULL AND b.telefone <> '')")
    if has_debt is True:
        conds.append("b.tem_divida = TRUE")

    where = " AND ".join(conds) if conds else "TRUE"
    return where, params


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
        "status": "ATIVA",  # busca indexes active establishments
        "has_debt": bool(r["has_debt"]) if r["has_debt"] is not None else False,
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

    where, params = _build_where(q, state, city, sector, size, has_debt, has_email, has_phone)

    count_sql = f"SELECT COUNT(*) FROM receita.busca b WHERE {where}"
    data_sql = (
        f"SELECT"
        f"  b.cnpj,"
        f"  COALESCE(NULLIF(TRIM(b.nome),''), b.razao_social) AS name,"
        f"  b.municipio_nome AS city,"
        f"  b.uf AS state,"
        f"  b.cnae_descricao AS sector,"
        f"  b.tem_divida AS has_debt"
        f" FROM receita.busca b"
        f" WHERE {where}"
        f" ORDER BY b.score DESC"
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
