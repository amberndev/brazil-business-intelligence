#!/usr/bin/env python3
"""
Local development seed script.

Creates all required tables (product schema + receita-equivalent tables)
and inserts fake data so the app can run end-to-end without the real
production database.

Usage (after `docker compose -f docker-compose.dev.yml up -d`):
    cd backend
    DATABASE_URL=postgresql://USER:PASSWORD@localhost:5433/DBNAME \\
        python scripts/seed.py
"""
from __future__ import annotations

import asyncio
import os
import sys

# Allow running as `python scripts/seed.py` from the backend directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_URL = os.environ["DATABASE_URL"]  # required — no credential default

DDL = """
-- ── product schema ────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS product;

CREATE TABLE IF NOT EXISTS product.api_keys (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    key                  TEXT        UNIQUE NOT NULL,
    name                 TEXT,
    email                TEXT,
    plan                 TEXT        NOT NULL DEFAULT 'FREE',
    requests_this_month  INT         NOT NULL DEFAULT 0,
    requests_limit       INT         NOT NULL DEFAULT 50,
    active               BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reset_at             TIMESTAMPTZ NOT NULL DEFAULT
                             DATE_TRUNC('month', NOW()) + INTERVAL '1 month'
);
CREATE INDEX IF NOT EXISTS idx_api_keys_key ON product.api_keys (key);

CREATE TABLE IF NOT EXISTS product.usage_events (
    id            BIGSERIAL   PRIMARY KEY,
    api_key_id    UUID        NOT NULL REFERENCES product.api_keys (id) ON DELETE CASCADE,
    endpoint      TEXT        NOT NULL,
    status_code   INT         NOT NULL,
    query_time_ms FLOAT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── receita-equivalent tables (fake schema, mirrors public Receita Federal format)
CREATE TABLE IF NOT EXISTS naturezas_juridicas (
    codigo    TEXT PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS cnaes (
    codigo    TEXT PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS municipios (
    codigo    TEXT PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS qualificacoes_socios (
    codigo    TEXT PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS empresas (
    cnpj_basico              TEXT PRIMARY KEY,
    razao_social             TEXT,
    natureza_juridica        TEXT,
    qualificacao_do_responsavel TEXT,
    capital_social           NUMERIC,
    porte_empresa            TEXT
);

CREATE TABLE IF NOT EXISTS estabelecimentos (
    cnpj_basico              TEXT,
    cnpj_ordem               TEXT,
    cnpj_dv                  TEXT,
    identificador_matriz_filial TEXT,
    nome_fantasia            TEXT,
    situacao_cadastral       TEXT,
    data_inicio_atividade    DATE,
    cnae_fiscal_principal    TEXT,
    cnae_fiscal_secundaria   TEXT,
    tipo_logradouro          TEXT,
    logradouro               TEXT,
    numero                   TEXT,
    complemento              TEXT,
    bairro                   TEXT,
    cep                      TEXT,
    uf                       TEXT,
    municipio                TEXT,
    ddd_telefone_1           TEXT,
    telefone_1               TEXT,
    email                    TEXT,
    PRIMARY KEY (cnpj_basico, cnpj_ordem, cnpj_dv)
);

CREATE TABLE IF NOT EXISTS socios (
    cnpj_basico              TEXT,
    identificador_de_socio   TEXT,
    nome_do_socio            TEXT,
    cnpj_cpf_do_socio        TEXT,
    qualificacao_do_socio    TEXT,
    data_entrada_sociedade   DATE
);

-- ── compliance tables (fake)
CREATE TABLE IF NOT EXISTS pgfn_divida_ativa (
    id               BIGSERIAL PRIMARY KEY,
    cnpj             TEXT,
    valor_consolidado NUMERIC DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cgu_ceis (
    id                       BIGSERIAL PRIMARY KEY,
    cnpj                     TEXT,
    tipo_sancao              TEXT,
    descricao_fundamentacao  TEXT,
    data_inicio_sancao       DATE,
    data_final_sancao        DATE
);

CREATE TABLE IF NOT EXISTS cgu_cnep (
    id                       BIGSERIAL PRIMARY KEY,
    cnpj                     TEXT,
    tipo_sancao              TEXT,
    descricao_fundamentacao  TEXT,
    data_inicio_sancao       DATE,
    data_final_sancao        DATE
);
"""

SEED_DATA = """
-- Reference data
INSERT INTO naturezas_juridicas VALUES ('2062', 'Sociedade Empresária Limitada') ON CONFLICT DO NOTHING;
INSERT INTO cnaes VALUES ('6201501', 'Desenvolvimento de programas de computador sob encomenda') ON CONFLICT DO NOTHING;
INSERT INTO cnaes VALUES ('4711302', 'Comércio varejista de mercadorias em geral') ON CONFLICT DO NOTHING;
INSERT INTO municipios VALUES ('7107', 'SAO PAULO') ON CONFLICT DO NOTHING;
INSERT INTO municipios VALUES ('6001', 'RIO DE JANEIRO') ON CONFLICT DO NOTHING;
INSERT INTO qualificacoes_socios VALUES ('49', 'Sócio-Administrador') ON CONFLICT DO NOTHING;

-- Company 1 (valid CNPJ 11222333000181)
INSERT INTO empresas VALUES ('11222333', 'EMPRESA DEMO LTDA', '2062', '49', 50000, '03') ON CONFLICT DO NOTHING;
INSERT INTO estabelecimentos VALUES (
    '11222333','0001','81','1','DEMO CO','2','2015-06-10',
    '6201501','6202300,6209100','RUA','JOSE ANTONIO','55','SALA 3',
    'CENTRO','04560000','SP','7107','11','988887777','contato@demo.com'
) ON CONFLICT DO NOTHING;
INSERT INTO socios VALUES ('11222333','1','JOAO SILVA','12345678901','49','2015-06-10') ON CONFLICT DO NOTHING;

-- Company 2 (valid CNPJ 11444777000161)
INSERT INTO empresas VALUES ('11444777', 'COMERCIO BRASIL SA', '2062', '49', 120000, '05') ON CONFLICT DO NOTHING;
INSERT INTO estabelecimentos VALUES (
    '11444777','0001','61','1','BRASIL SHOP','2','2018-03-22',
    '4711302','','RUA','DA LIBERDADE','200',NULL,
    'CENTRO','01503001','SP','7107','11','912345678','contato@brasil.com'
) ON CONFLICT DO NOTHING;
-- PGFN debt for company 2
INSERT INTO pgfn_divida_ativa (cnpj, valor_consolidado) VALUES ('11444777000161', 85000) ON CONFLICT DO NOTHING;

-- Product keys (dev only)
INSERT INTO product.api_keys (key, name, email, plan, requests_limit)
VALUES
  ('bbi_dev_free_key_0000000000000000', 'Dev FREE',       'free@dev.local',       'FREE',       50),
  ('bbi_dev_starter_key_000000000000', 'Dev STARTER',    'starter@dev.local',    'STARTER',    2000),
  ('bbi_dev_pro_key_00000000000000000', 'Dev PRO',        'pro@dev.local',        'PRO',        15000),
  ('bbi_dev_enterprise_key_000000000', 'Dev ENTERPRISE', 'enterprise@dev.local', 'ENTERPRISE', -1)
ON CONFLICT (key) DO NOTHING;
"""


async def main() -> None:
    import asyncpg
    print(f"Connecting to {DATABASE_URL.split('@')[-1]} …")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("Creating tables …")
        await conn.execute(DDL)
        print("Inserting seed data …")
        await conn.execute(SEED_DATA)
        print("✓ Seed complete.")
        print("\nDev API keys:")
        rows = await conn.fetch("SELECT key, plan FROM product.api_keys ORDER BY plan")
        for r in rows:
            print(f"  {r['plan']:12s}  {r['key']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
