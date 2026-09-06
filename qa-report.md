# QA Report — Produção VPS (worbita-dados) · brazil.ambern.dev

**Escopo:** verificação READ-ONLY do deploy do Brazil Business Intelligence na VPS de produção via `ssh worbita-dados`. Nenhum comando de mutação executado (só `systemctl status/is-active`, `ss -tlnp`, leitura de config do Caddy, `journalctl` leitura). Segredos/keys/senhas/IPs sensíveis redigidos.

**Data:** 2026-09-06 · **Host:** worbita-dados (Ubuntu 6.8.0, x86_64) · **Reviewer:** oc-qa (pane-64)

**Veredito geral: PASS (5/5)** — 1 finding baixo/informativo (F-400).

---

## Check 1 — systemd units bbi-api e bbi-web ativos/running → ✅ PASS
Evidência (`systemctl is-active` + `status --no-pager`):
- `bbi-api`: **active (running)** desde 2026-09-06 02:09:50, Main PID 2704438 (uvicorn, 2 workers), Loaded/enabled. CMD confere com o unit de referência: `--host 127.0.0.1 --port 8100 --workers 2`.
- `bbi-web`: **active (running)** desde 2026-09-06 02:11:31, Main PID 2705575 (`next-server v16.3.4`), Loaded/enabled.
- Impacto: ambos serviços da app no ar.

## Check 2 — portas da app ligadas SÓ em 127.0.0.1, nunca 0.0.0.0 → ✅ PASS
Evidência (`ss -H -tlnp`):
- `127.0.0.1:8100` → uvicorn (backend) ✓ localhost-only
- `127.0.0.1:3100` → next-server (frontend) ✓ localhost-only
- `127.0.0.1:6379` → redis-server ✓ localhost-only
- Únicas portas públicas na tabela: `*:22` (SSH), `*:80` e `*:443` (Caddy) — esperado. Nenhuma porta da app exposta em 0.0.0.0.
- Impacto: backend/frontend/redis inacessíveis direto da internet; só via Caddy (443). Superfície de ataque correta.

## Check 3 — bloco Caddy de brazil.ambern.dev sano → ✅ PASS
Evidência (`/etc/caddy/conf.d/brazil.ambern.dev.caddy`, importado por `/etc/caddy/Caddyfile`):
- `handle_path /api/*` → `reverse_proxy 127.0.0.1:8100` (strip do prefixo /api, correto p/ rotas /v1 do backend)
- `handle` (resto) → `reverse_proxy 127.0.0.1:3100` (frontend)
- TLS automático (Let's Encrypt). Bloco idêntico ao snippet de referência.
- `caddy validate` → **Valid configuration**; auto-HTTPS + redirect HTTP→HTTPS habilitados.
- Cert provisionado: `brazil.ambern.dev.crt` / `.key` / `.json` presentes no storage do Caddy.
- Impacto: roteamento e TLS corretos; site servido com HTTPS válido.

## Check 4 — serviços pré-existentes `worbita` intactos → ✅ PASS
Evidência (`systemctl list-units`/`is-active`):
- `worbita-app.service`: **active (running)** ✓
- `worbita-atualizacao.service` / `worbita-pgfn.service`: `inactive (dead)` — **normal**, são oneshot disparados por timer; os timers `worbita-atualizacao.timer` e `worbita-pgfn.timer` estão **active**.
- Impacto: deploy do BBI não perturbou o Worbita; app e agendamentos preservados.

## Check 5 — journalctl bbi-api/bbi-web sem segredos vazados → ✅ PASS
Evidência (scan `journalctl` com grep -c por `api_key|secret|password|token|bearer|authorization|postgres://|redis://|sk-…|AKIA`):
- `bbi-api`: 17 linhas, **0** matches de padrão de segredo.
- `bbi-web`: 96 linhas, **0** matches.
- Eyeball dos tails (redigido): logs são só requests HTTP (health 200, chamadas não-autenticadas 401 — auth funcionando) e boot do Next.js. Nenhuma env/chave impressa.
- Impacto: sem exposição de credenciais nos logs.

---

## Findings (lane F400–F499)
| ID | Sev | Categoria | Resumo | Status |
|----|-----|-----------|--------|--------|
| F-400 | baixa | performance | bbi-web logou `Failed with result 'exit-code'` no restart do deploy; auto-recuperou e está healthy agora | aberto |

### Observações não-defeito (sem finding)
- Backend loga IPs públicos com porta `:0` em `/v1/*` — é o X-Forwarded-For do Caddy (proxy-headers). Requests chegam via Caddy; porta 8100 confirmada localhost-only. Sem risco.
- Ruído de scanner na internet (`POST /graphql`, `/gql` → 404) — inofensivo.
