#!/usr/bin/env bash
# Brazil Business Intelligence — production deploy script
# Idempotent. Logs every state-changing command. Non-interactive.
# Usage:
#   export BBI_SSH_ALIAS=worbita-dados   # optional; default = worbita-dados
#   export CONTACT_EMAIL=you@example.com # required
#   bash deploy/deploy.sh
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SSH_ALIAS="${BBI_SSH_ALIAS:-worbita-dados}"
DEPLOY_TARGET="/opt/brazil-business-intelligence"

# Validate required local env vars before doing anything
: "${CONTACT_EMAIL:?ERROR: CONTACT_EMAIL must be set (e.g. export CONTACT_EMAIL=ops@example.com)}"

# ── Logging ──────────────────────────────────────────────────────────────────
log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }
log "==> BBI deploy starting (target: ${SSH_ALIAS}:${DEPLOY_TARGET})"

# ── 1. Sync repo to server ────────────────────────────────────────────────────
log "==> [1/8] Syncing repo to ${SSH_ALIAS}:${DEPLOY_TARGET} ..."
ssh "${SSH_ALIAS}" "sudo mkdir -p ${DEPLOY_TARGET} && sudo chown -R \$(id -u):\$(id -g) ${DEPLOY_TARGET}"
tar -czf - \
    --exclude='.git' \
    --exclude='.overclock-app' \
    --exclude='messages.db' \
    --exclude='frontend/.next' \
    --exclude='frontend/node_modules' \
    --exclude='backend/.venv' \
    --exclude='backend/__pycache__' \
    --exclude='backend/.pytest_cache' \
    --exclude='*.pyc' \
    -C "${REPO_ROOT}" . | \
    ssh "${SSH_ALIAS}" "tar -xzf - -C ${DEPLOY_TARGET}"

# ── 2–8. Remote provisioning (single SSH session) ────────────────────────────
log "==> Initiating remote provisioning session ..."
ssh "${SSH_ALIAS}" bash -s -- "${CONTACT_EMAIL}" << 'REMOTE_EOF'
set -euo pipefail
CONTACT_EMAIL="$1"
DEPLOY_TARGET="/opt/brazil-business-intelligence"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }

# ── 2. Backend virtualenv + pip install ──────────────────────────────────────
log "==> [2/8] Backend venv + pip install ..."
sudo apt-get install -y python3.12-venv
python3.12 -m venv "${DEPLOY_TARGET}/backend/.venv"
log "    pip install requirements ..."
"${DEPLOY_TARGET}/backend/.venv/bin/pip" install --quiet --upgrade pip
"${DEPLOY_TARGET}/backend/.venv/bin/pip" install --quiet -r "${DEPLOY_TARGET}/backend/requirements.txt"

# ── 3. Frontend: npm ci + next build ─────────────────────────────────────────
log "==> [3/8] Frontend npm ci + next build ..."
cd "${DEPLOY_TARGET}/frontend"
npm ci --silent
log "    next build (NEXT_PUBLIC_API_URL baked into bundle) ..."
NEXT_PUBLIC_API_URL='https://brazil.ambern.dev/api' npm run build
cd /

# ── 4. Redis: install + bind to 127.0.0.1 ────────────────────────────────────
log "==> [4/8] Redis-server install + bind 127.0.0.1 ..."
sudo apt-get install -y redis-server

REDIS_CONF=/etc/redis/redis.conf
if sudo grep -qE '^bind ' "${REDIS_CONF}"; then
    log "    Updating bind directive in ${REDIS_CONF} ..."
    sudo sed -i 's/^bind .*/bind 127.0.0.1/' "${REDIS_CONF}"
else
    log "    Adding bind 127.0.0.1 to ${REDIS_CONF} ..."
    echo 'bind 127.0.0.1' | sudo tee -a "${REDIS_CONF}" > /dev/null
fi
log "    Enabling + restarting redis-server ..."
sudo systemctl enable redis-server
sudo systemctl restart redis-server

# ── 5. Write /opt/brazil-business-intelligence/.env (no secret logging) ──────
log "==> [5/8] Deriving DATABASE_URL and writing .env ..."
# Read RECEITA_DATABASE_URL from the existing worbita app env — NEVER echo/log it
_DB_URL="$(grep '^RECEITA_DATABASE_URL=' /opt/worbita/app/.env | cut -d'=' -f2-)"
if [ -z "${_DB_URL}" ]; then
    echo "FATAL: RECEITA_DATABASE_URL not found in /opt/worbita/app/.env" >&2
    exit 1
fi

# Write .env without echoing the sensitive value
log "    Writing ${DEPLOY_TARGET}/.env (DATABASE_URL value not logged) ..."
{
    printf 'DATABASE_URL=%s\n'                          "${_DB_URL}"
    printf 'REDIS_URL=redis://127.0.0.1:6379/0\n'
    printf 'CONTACT_EMAIL=%s\n'                         "${CONTACT_EMAIL}"
    printf 'NEXT_PUBLIC_API_URL=https://brazil.ambern.dev/api\n'
    printf 'CORS_ORIGINS=https://brazil.ambern.dev,http://localhost:3100\n'
    printf 'API_ENV=production\n'
} | sudo tee "${DEPLOY_TARGET}/.env" > /dev/null
sudo chmod 600 "${DEPLOY_TARGET}/.env"

# ── 6. Apply product schema DDL (idempotent; NO seed data) ───────────────────
log "==> [6/8] Applying product schema DDL ..."
# NOTE: DATABASE_URL must have CREATE SCHEMA / CREATE TABLE privileges on the
# worbita database. If prospecta_readonly lacks DDL permissions, have a DBA
# apply backend/migrations/001_product_schema.sql manually with a privileged
# role before this step runs; the IF NOT EXISTS guards make re-runs safe.
if "${DEPLOY_TARGET}/backend/.venv/bin/python" - "${_DB_URL}" \
        "${DEPLOY_TARGET}/backend/migrations/001_product_schema.sql" << 'PYEOF'
import asyncio, asyncpg, sys

async def main():
    db_url = sys.argv[1]
    ddl_path = sys.argv[2]
    with open(ddl_path) as fh:
        ddl = fh.read()
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(ddl)
        print("    Schema DDL applied OK")
    finally:
        await conn.close()

asyncio.run(main())
PYEOF
then
    log "    Product schema applied."
else
    echo "WARNING: Schema DDL step failed (see above). The role may lack DDL" >&2
    echo "         permissions — apply migrations/001_product_schema.sql manually." >&2
    echo "         Continuing; the rest of the deploy does NOT depend on this." >&2
fi

unset _DB_URL

# ── 7. Systemd units: install, daemon-reload, enable, start ──────────────────
log "==> [7/8] Installing systemd units ..."
sudo cp "${DEPLOY_TARGET}/deploy/bbi-api.service" /etc/systemd/system/bbi-api.service
sudo cp "${DEPLOY_TARGET}/deploy/bbi-web.service" /etc/systemd/system/bbi-web.service
log "    daemon-reload ..."
sudo systemctl daemon-reload
log "    Enabling + starting bbi-api ..."
sudo systemctl enable bbi-api
sudo systemctl restart bbi-api
log "    Enabling + starting bbi-web ..."
sudo systemctl enable bbi-web
sudo systemctl restart bbi-web

# ── 8. DNS guard → Caddy snippet or staged escalation ────────────────────────
log "==> [8/8] DNS guard + Caddy ..."
SNIPPET="${DEPLOY_TARGET}/deploy/Caddyfile.brazil.snippet"
CADDY_CONF_DIR="/etc/caddy/conf.d"
CADDY_DEST="${CADDY_CONF_DIR}/brazil.ambern.dev.caddy"

VPS_IP="$(curl -fsSL --max-time 5 https://api.ipify.org || true)"
DNS_IP="$(getent hosts brazil.ambern.dev | awk '{print $1}' | head -1 || true)"

log "    VPS public IP : ${VPS_IP:-UNKNOWN}"
log "    DNS resolution: ${DNS_IP:-UNRESOLVED}"

if [ -n "${VPS_IP}" ] && [ -n "${DNS_IP}" ] && [ "${VPS_IP}" = "${DNS_IP}" ]; then
    log "    DNS verified. Deploying Caddy snippet ..."
    sudo mkdir -p "${CADDY_CONF_DIR}"
    sudo cp "${SNIPPET}" "${CADDY_DEST}"
    # Ensure main Caddyfile imports conf.d (idempotent)
    if ! sudo grep -q 'import /etc/caddy/conf.d' /etc/caddy/Caddyfile; then
        log "    Adding import directive to /etc/caddy/Caddyfile ..."
        echo '' | sudo tee -a /etc/caddy/Caddyfile > /dev/null
        echo 'import /etc/caddy/conf.d/*.caddy' | sudo tee -a /etc/caddy/Caddyfile > /dev/null
    fi
    log "    Validating Caddyfile ..."
    sudo caddy validate --config /etc/caddy/Caddyfile
    log "    Reloading Caddy ..."
    sudo systemctl reload caddy

    # Smoke: HTTPS
    sleep 5
    log "    Smoke check: HTTPS /api/v1/health ..."
    curl -fsS --max-time 10 "https://brazil.ambern.dev/api/v1/health" \
        && log "    HTTPS health OK" \
        || log "WARNING: HTTPS check failed — TLS cert may still be provisioning"
else
    log "!!! DNS MISMATCH — Caddy NOT reloaded."
    log "!!! brazil.ambern.dev resolves to '${DNS_IP:-UNRESOLVED}' but VPS IP is '${VPS_IP:-UNKNOWN}'"
    log "!!! Snippet staged at: ${SNIPPET}"
    log "!!!"
    log "!!! ESCALATION — when DNS propagates, run on the server:"
    log "!!!   sudo mkdir -p ${CADDY_CONF_DIR}"
    log "!!!   sudo cp ${SNIPPET} ${CADDY_DEST}"
    log "!!!   # Add 'import /etc/caddy/conf.d/*.caddy' to /etc/caddy/Caddyfile if not present"
    log "!!!   sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy"
fi

# ── Local smoke (always) ──────────────────────────────────────────────────────
log "==> Smoke checks (localhost) ..."
sleep 3
log "    Backend /v1/health ..."
curl -fsS --max-time 10 http://localhost:8100/v1/health \
    && log "    Backend OK" \
    || { log "ERROR: backend health check failed"; exit 1; }

log "    Frontend port 3100 ..."
curl -fsS --max-time 10 -o /dev/null -w "    Frontend HTTP %{http_code}\n" http://localhost:3100 \
    || { log "ERROR: frontend check failed"; exit 1; }

log "==> Deploy complete."
REMOTE_EOF

log "==> Local deploy script finished."
