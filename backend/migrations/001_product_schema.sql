-- Brazil Business Intelligence — product schema
-- Run once against the shared database (same DATABASE_URL).
-- TODO(ops): split into a dedicated product_user role after launch.

CREATE SCHEMA IF NOT EXISTS product;

-- ── API keys ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS product.api_keys (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    key              TEXT        UNIQUE NOT NULL,
    name             TEXT,
    email            TEXT,
    plan             TEXT        NOT NULL DEFAULT 'FREE',
                                 -- FREE | STARTER | PRO | ENTERPRISE
    requests_this_month  INT     NOT NULL DEFAULT 0,
    requests_limit       INT     NOT NULL DEFAULT 50,
    active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reset_at         TIMESTAMPTZ NOT NULL DEFAULT
                         DATE_TRUNC('month', NOW()) + INTERVAL '1 month'
);

CREATE INDEX IF NOT EXISTS idx_api_keys_key ON product.api_keys (key);

-- Add email column idempotently for clusters upgraded from pre-email schema
ALTER TABLE product.api_keys ADD COLUMN IF NOT EXISTS email TEXT;

-- Enforce one active FREE key per email (FINDING 2)
CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_email_free_active
    ON product.api_keys (lower(email))
    WHERE plan = 'FREE' AND active = TRUE;

-- ── Usage events (audit / analytics) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS product.usage_events (
    id           BIGSERIAL   PRIMARY KEY,
    api_key_id   UUID        NOT NULL REFERENCES product.api_keys (id) ON DELETE CASCADE,
    endpoint     TEXT        NOT NULL,
    status_code  INT         NOT NULL,
    query_time_ms FLOAT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_events_key_ts
    ON product.usage_events (api_key_id, created_at DESC);

-- ── Seed a free test key (dev only — remove before production) ───────────────
-- INSERT INTO product.api_keys (key, name, email, plan, requests_limit)
-- VALUES ('bbi_dev_test_key_replace_me_000000', 'Dev test', 'dev@example.com', 'PRO', 15000);
