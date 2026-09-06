"""
Company endpoints:
  GET  /v1/company/{cnpj}               — CompanyProfile (FREE+)
  GET  /v1/company/{cnpj}/compliance    — CompanyCompliance (STARTER+)
  GET  /v1/company/{cnpj}/shareholders  — CompanyShareholders (STARTER+)
  POST /v1/company/batch                — BatchResponse (STARTER+, max 50)

SQL note: column names follow the Receita Federal public-data format.
TODO(backend): verify every column name against the live schema before deploy.
"""
from __future__ import annotations

import asyncio
import csv
import io
import re
import secrets
import time
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from ..auth import (
    after_usage,
    get_api_key,
    check_rate_limit,
    make_meta,
    record_usage,
    require_plan,
    set_ratelimit_headers,
)
from ..db import get_pool

router = APIRouter(tags=["company"])

# ── CNPJ helpers ─────────────────────────────────────────────────────────────

_ALL_SAME = {d * 14 for d in "0123456789"}


def normalize_cnpj(raw: str) -> str:
    """Strip mask, validate check digits. Returns 14-digit string or raises ValueError."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 14 or digits in _ALL_SAME:
        raise ValueError("invalid_cnpj")

    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def _digit(d: str, w: list[int]) -> int:
        remainder = sum(int(c) * wt for c, wt in zip(d, w)) % 11
        return 0 if remainder < 2 else 11 - remainder

    if int(digits[12]) != _digit(digits[:12], weights1):
        raise ValueError("invalid_cnpj")
    if int(digits[13]) != _digit(digits[:13], weights2):
        raise ValueError("invalid_cnpj")

    return digits


def format_cnpj(digits: str) -> str:
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


# ── Status / size maps ────────────────────────────────────────────────────────

_STATUS_MAP = {"1": "BAIXADA", "2": "ATIVA", "3": "SUSPENSA", "4": "SUSPENSA", "8": "BAIXADA"}
# porte is stored as smallint (1=ME, 3=EPP, 5=MEDIO/GRANDE) in receita.empresas
_SIZE_MAP   = {"1": "ME", "3": "EPP", "5": "MEDIO"}
# TODO(backend): MEI identified by natureza_juridica = '2135' or porte '01' in some datasets.
# TODO(backend): GRANDE not available in Receita porte field; derive from revenue/employees if needed.


def _map_status(code: Any) -> str:
    return _STATUS_MAP.get(str(code).strip(), "BAIXADA")


def _map_size(code: Any) -> str | None:
    return _SIZE_MAP.get(str(code).strip()) if code else None


def _or_none(val: Any) -> Any:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _format_phone(ddd: Any, number: Any) -> str | None:
    d = _or_none(ddd)
    n = _or_none(number)
    if not n:
        return None
    return f"+55{d}{n}" if d else n


# ── SQL — company profile ─────────────────────────────────────────────────────
# TODO(backend): verify table/schema names (receita.*, public.*, etc.) against live DB.
# Column names follow the standard Receita Federal CSV import format.

_COMPANY_PROFILE_SQL = """
SELECT
    em.razao_social,
    es.nome_fantasia,
    es.situacao_cadastral,
    em.porte,
    es.data_inicio_atividade,
    em.capital_social,
    nj.descricao           AS natureza_juridica_desc,
    es.cnae_fiscal_principal,
    cn.descricao           AS cnae_principal_desc,
    es.tipo_logradouro,
    es.logradouro,
    es.numero,
    es.complemento,
    es.bairro,
    es.cep,
    es.uf,
    mu.descricao           AS municipio_desc,
    es.ddd1,
    es.telefone1,
    es.correio_eletronico,
    ARRAY_TO_STRING(COALESCE(es.cnae_fiscal_secundaria, '{}'), ',') AS cnae_secundaria_raw
FROM receita.estabelecimentos es
JOIN receita.empresas em
    ON em.cnpj_basico = es.cnpj_basico
LEFT JOIN receita.naturezas_juridicas nj
    ON nj.codigo = em.natureza_juridica
LEFT JOIN receita.cnaes cn
    ON cn.codigo = es.cnae_fiscal_principal
LEFT JOIN receita.municipios mu
    ON mu.codigo = es.municipio
WHERE es.cnpj_basico = $1 AND es.cnpj_ordem = $2 AND es.cnpj_dv = $3
  AND es.identificador_matriz_filial = 1
"""


def _build_profile(row: Any, cnpj: str) -> dict:
    cnae_code = _or_none(row["cnae_fiscal_principal"])
    cnae_desc = _or_none(row["cnae_principal_desc"])

    # Secondary CNAEs: parse comma-separated list if present.
    secondary: list[dict] = []
    raw_sec = _or_none(row["cnae_secundaria_raw"])
    if raw_sec:
        for code in raw_sec.split(","):
            code = code.strip()
            if code:
                secondary.append({"code": code, "description": None})

    date_raw = row["data_inicio_atividade"]
    opened_at = date_raw.isoformat() if date_raw else None

    capital = row["capital_social"]
    share_capital = float(capital) if capital is not None else None

    tipo = _or_none(row["tipo_logradouro"])
    logr = _or_none(row["logradouro"])
    street = f"{tipo} {logr}".strip() if tipo and logr else (logr or tipo)

    return {
        "cnpj": cnpj,
        "cnpj_formatted": format_cnpj(cnpj),
        "razao_social": _or_none(row["razao_social"]) or "",
        "nome_fantasia": _or_none(row["nome_fantasia"]),
        "status": _map_status(row["situacao_cadastral"]),
        "size": _map_size(row["porte"]),
        "opened_at": opened_at,
        "legal_nature": _or_none(row["natureza_juridica_desc"]),
        "share_capital": share_capital,
        "location": {
            "street": street,
            "number": _or_none(row["numero"]),
            "complement": _or_none(row["complemento"]),
            "district": _or_none(row["bairro"]),
            "city": _or_none(row["municipio_desc"]),
            "state": _or_none(row["uf"]),
            "zip": _or_none(row["cep"]),
        },
        "sector": {
            "primary_cnae": {"code": cnae_code, "description": cnae_desc} if cnae_code else None,
            "secondary_cnae": secondary,
        },
        "contact": {
            "phone": _format_phone(row["ddd1"], row["telefone1"]),
            "email": _or_none(row["correio_eletronico"]),
        },
    }


# ── SQL — compliance (PGFN + CGU) ─────────────────────────────────────────────
# TODO(backend): verify actual table/column names for PGFN and CGU in the live schema.

_PGFN_SQL = """
SELECT
    inscricoes            AS records_count,
    COALESCE(valor_total, 0) AS total_amount
FROM pgfn.divida_por_cnpj
WHERE cnpj = $1
"""

_CGU_SQL = """
SELECT
    categoria            AS type,
    fundamentacao        AS description,
    data_inicio          AS start_date,
    data_final           AS end_date
FROM cgu.sancao_empresa
WHERE cnpj = $1
"""


def _build_compliance(cnpj: str, pgfn_row: Any, cgu_rows: list) -> dict:
    records_count = int(pgfn_row["records_count"]) if pgfn_row else 0
    total_amount = float(pgfn_row["total_amount"]) if pgfn_row else 0.0

    items = []
    for r in (cgu_rows or []):
        start = r["start_date"]
        end = r["end_date"]
        items.append({
            "type": _or_none(r["type"]) or "",
            "description": _or_none(r["description"]),
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
        })

    return {
        "cnpj": cnpj,
        "pgfn_debt": {
            "has_debt": records_count > 0,
            "total_amount": total_amount,
            "records_count": records_count,
        },
        "cgu_sanctions": {
            "has_sanctions": len(items) > 0,
            "count": len(items),
            "items": items,
        },
    }


# ── Routes ────────────────────────────────────────────────────────────────────

def _raise_invalid_cnpj() -> None:
    raise HTTPException(
        status_code=422,
        detail={"code": "invalid_cnpj", "message": "CNPJ failed check-digit validation.", "status": 422},
    )


@router.get("/company/{cnpj}", response_model=None)
async def get_company_profile(
    cnpj: str,
    response: Response,
    key_info: dict[str, Any] = Depends(get_api_key),
) -> dict:
    # Plan gate: FREE+ (all plans permitted — no additional check needed)
    try:
        normalized = normalize_cnpj(cnpj)
    except ValueError:
        _raise_invalid_cnpj()

    requests_remaining = await check_rate_limit(key_info)

    t0 = time.perf_counter()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_COMPANY_PROFILE_SQL, normalized[:8], normalized[8:12], normalized[12:])
    query_time_ms = (time.perf_counter() - t0) * 1000

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "CNPJ not found in database.", "status": 404},
        )

    await record_usage(key_info)
    set_ratelimit_headers(response, key_info, after_usage(requests_remaining))

    return {
        "data": _build_profile(row, normalized),
        "meta": make_meta(key_info, after_usage(requests_remaining), query_time_ms),
    }


@router.get("/company/{cnpj}/compliance", response_model=None)
async def get_company_compliance(
    cnpj: str,
    response: Response,
    key_info: dict[str, Any] = Depends(require_plan("STARTER")),
) -> dict:
    try:
        normalized = normalize_cnpj(cnpj)
    except ValueError:
        _raise_invalid_cnpj()

    requests_remaining = await check_rate_limit(key_info)

    t0 = time.perf_counter()
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify company exists first
        exists = await conn.fetchval(
            "SELECT 1 FROM receita.estabelecimentos es"
            " WHERE es.cnpj_basico = $1 AND es.cnpj_ordem = $2 AND es.cnpj_dv = $3"
            " AND es.identificador_matriz_filial = 1",
            normalized[:8], normalized[8:12], normalized[12:],
        )
        if not exists:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "CNPJ not found in database.", "status": 404},
            )
        pgfn_row = await conn.fetchrow(_PGFN_SQL, normalized)
        cgu_rows = await conn.fetch(_CGU_SQL, normalized)
    query_time_ms = (time.perf_counter() - t0) * 1000

    await record_usage(key_info)
    set_ratelimit_headers(response, key_info, after_usage(requests_remaining))

    return {
        "data": _build_compliance(normalized, pgfn_row, list(cgu_rows)),
        "meta": make_meta(key_info, after_usage(requests_remaining), query_time_ms),
    }


# ── Shareholders ──────────────────────────────────────────────────────────────

_SHAREHOLDERS_SQL = """
SELECT
    s.nome_socio                            AS name,
    s.cnpj_cpf_do_socio                     AS document_raw,
    qs.descricao                            AS role,
    s.data_entrada_sociedade                AS since_raw
FROM receita.socios s
LEFT JOIN receita.qualificacoes_socios qs ON qs.codigo = s.qualificacao_do_socio
WHERE s.cnpj_basico = $1
ORDER BY s.nome_socio
"""
# TODO(backend): verify socios / qualificacoes_socios column names against live schema.
# TODO(backend): participation_pct — not available in Receita Federal data; left null.


def _mask_document(raw: Any) -> str | None:
    """Mask CPF as ***.***.XXX-XX; pass CNPJ through formatted; reject unknowns."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 11:  # CPF
        return f"***.***.{digits[6:9]}-{digits[9:11]}"
    if len(digits) == 14:  # Corporate partner CNPJ (public info)
        return format_cnpj(digits)
    return None  # unknown length — never expose raw


def _build_shareholders(cnpj: str, rows: list) -> dict:
    shareholders = []
    for r in rows:
        since_raw = r["since_raw"]
        shareholders.append({
            "name": _or_none(r["name"]) or "",
            "document": _mask_document(r["document_raw"]),
            "role": _or_none(r["role"]),
            "participation_pct": None,  # TODO(backend): not in Receita Federal base data
            "since": since_raw.isoformat() if since_raw else None,
        })
    return {"cnpj": cnpj, "count": len(shareholders), "shareholders": shareholders}


@router.get("/company/{cnpj}/shareholders", response_model=None)
async def get_company_shareholders(
    cnpj: str,
    response: Response,
    key_info: dict[str, Any] = Depends(require_plan("STARTER")),
) -> dict:
    try:
        normalized = normalize_cnpj(cnpj)
    except ValueError:
        _raise_invalid_cnpj()

    requests_remaining = await check_rate_limit(key_info)

    cnpj_basico = normalized[:8]

    t0 = time.perf_counter()
    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM receita.estabelecimentos es"
            " WHERE es.cnpj_basico = $1 AND es.identificador_matriz_filial = 1",
            cnpj_basico,
        )
        if not exists:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "CNPJ not found in database.", "status": 404},
            )
        rows = await conn.fetch(_SHAREHOLDERS_SQL, cnpj_basico)
    query_time_ms = (time.perf_counter() - t0) * 1000

    await record_usage(key_info)
    set_ratelimit_headers(response, key_info, after_usage(requests_remaining))

    return {
        "data": _build_shareholders(normalized, list(rows)),
        "meta": make_meta(key_info, after_usage(requests_remaining), query_time_ms),
    }


# ── Batch ─────────────────────────────────────────────────────────────────────

@router.post("/company/batch", response_model=None)
async def post_company_batch(
    response: Response,
    body: dict[str, Any] = Body(...),
    key_info: dict[str, Any] = Depends(require_plan("STARTER")),
) -> dict:
    cnpjs_raw: list = body.get("cnpjs", [])

    if not cnpjs_raw:
        raise HTTPException(
            status_code=422,
            detail={"code": "batch_empty", "message": "cnpjs list must not be empty.", "status": 422},
        )
    if len(cnpjs_raw) > 50:
        raise HTTPException(
            status_code=422,
            detail={"code": "batch_too_large", "message": "Batch limit is 50 CNPJs.", "status": 422},
        )

    requests_remaining = await check_rate_limit(key_info)  # counts as 1 request

    t0 = time.perf_counter()
    pool = await get_pool()

    results: list[dict] = []
    async with pool.acquire() as conn:
        for raw in cnpjs_raw:
            try:
                normalized = normalize_cnpj(str(raw))
            except ValueError:
                results.append({
                    "cnpj": re.sub(r"\D", "", str(raw)),
                    "profile": None,
                    "error": {"code": "invalid_cnpj", "message": "CNPJ failed check-digit validation."},
                })
                continue

            row = await conn.fetchrow(_COMPANY_PROFILE_SQL, normalized[:8], normalized[8:12], normalized[12:])
            if row is None:
                results.append({
                    "cnpj": normalized,
                    "profile": None,
                    "error": {"code": "not_found", "message": "CNPJ not found in database."},
                })
            else:
                results.append({
                    "cnpj": normalized,
                    "profile": _build_profile(row, normalized),
                    "error": None,
                })

    query_time_ms = (time.perf_counter() - t0) * 1000

    await record_usage(key_info)
    set_ratelimit_headers(response, key_info, after_usage(requests_remaining))

    return {
        "data": {"count": len(results), "results": results},
        "meta": make_meta(key_info, after_usage(requests_remaining), query_time_ms),
    }
