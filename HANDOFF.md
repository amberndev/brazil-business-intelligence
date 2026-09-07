# HANDOFF — Brazil Business Intelligence

Última atualização: **2026-09-06** (fim da sessão na máquina A, antes de trocar de máquina).
Leia este arquivo primeiro ao retomar o trabalho em outra máquina.

---

## 1. Onde estamos

Produto: API + web app de dados de empresas brasileiras (base Receita Federal).

| Item | Valor |
| --- | --- |
| Repositório | `github.com/amberndev/brazil-business-intelligence` |
| Branch | `master` |
| Produção | https://brazil.ambern.dev |
| VPS | alias SSH `worbita-dados` |
| Serviços | systemd `bbi-api`, `bbi-web` (ver `deploy/`) |
| Proxy | Caddy — `deploy/Caddyfile.brazil.snippet` |
| Banco | PostgreSQL local `worbita` (auth peer via `sudo -u postgres psql`) |

**Produção está no ar e saudável**, mas com bugs funcionais abertos (seção 3).

---

## 2. O que acabou de ser commitado (WIP desta sessão)

Todo o trabalho em andamento foi commitado e enviado ao `origin/master`. Nada ficou só na máquina A.

### Backend
- **`backend/app/routers/search.py`** — reescrita dos filtros de `/v1/search`:
  - `q` com 14 dígitos é detectado como CNPJ e vai direto na PK (`b.cnpj = $n`), em vez de full-text.
  - `city` normalizado (remoção de acentos, NFD) e resolvido via subquery em `receita.municipios` em vez de `ILIKE` em `municipio_nome`.
  - `has_email` / `has_phone` / `has_debt` viraram **tri-state** (`true` / `false` / omitido). `has_phone` considera `telefone` **ou** `telefone_2`. `has_debt=true` mantém o predicado literal `= TRUE` para continuar usando o índice parcial `busca_divida`.
  - `has_debt` NULL passou a ser preservado no resultado (JSON `null`), em vez de virar `false`.
  - `status`: apenas `ATIVA` é suportado; `BAIXADA`/`SUSPENSA` retornam `422 unsupported_filter` (o dataset só contém ativas).
  - **`ORDER BY` condicional** (o fix que fechou a F-103): `b.score DESC` só quando existe `q`; sem `q`, `b.cnpj` (btree da PK). Sem isso, a busca padrão fazia seq-scan + sort externo em 72M linhas e estourava o `command_timeout=30` do asyncpg.
- **`backend/app/main.py`** — handler de exceção não tratada devolvendo o envelope de erro do contrato (`{"error":{"code","message","status"}}`) em vez de `Internal Server Error` texto puro → endereça **F-105**.
- **`backend/app/routers/company.py`** — limpeza pontual.
- Novos testes: `backend/tests/test_search_filter_contract.py`, `test_search_regressions.py`, `test_unhandled_errors.py`.
- **`backend/SEARCH_DATASET_AUDIT.md`** — auditoria read-only do dataset (feita via SSH, sem alterar produção). Conteúdo-chave:
  - `receita.busca` é tabela física, ~28,1M linhas, 26 colunas, 9 índices.
  - O ETL (`006-tabela-de-busca.sql`, `022-rebuild-mensal.sql`) filtra `situacao_cadastral = 2` → só empresas ativas.
  - **A página de dados é rápida** (`ORDER BY b.cnpj LIMIT 20` → 1,67 ms via `busca_pkey`), **o gargalo é o `COUNT(*)` exato** que roda antes: `COUNT(*) WHERE TRUE` custa ~315k (index-only scan da base inteira) e `COUNT(*) WHERE tem_divida = FALSE` custa ~1,48M (parallel seq scan). É isso que estoura o timeout de 30–41s da F-103.

### Frontend
- Landing extraída de `page.tsx`/`layout.tsx` para **`src/app/Landing.tsx` + `Landing.module.css`** (page.tsx −485 linhas, layout.tsx −169). Inclui contexto de idioma pt-BR/en.
- `src/lib/api.ts`, `src/app/app/search/page.tsx`, `src/app/app/company/[cnpj]/page.tsx`, `globals.css` ajustados.
- Novos specs Playwright: `frontend/tests/key-validation.spec.ts`, `frontend/tests/search-ux.spec.ts`.
- `frontend/public/assets/` adicionado.

### Limpeza (2026-09-07)
- `backend/app/routers/search.py.new` **apagado** — era a versão anterior ao fix (sem detecção de CNPJ, `municipio_nome ILIKE`, `has_email is True`), superada pelo `search.py` atual.
- Arquivos de 0 byte de redirecionamento de shell quebrado (`HTTPS`, `bool`, `limit`, `backend/str`, `frontend/should`) **apagados e a deleção commitada** — estavam versionados por acidente.
- `frontend/test-results/` passou para o `.gitignore`.
- `.codex/` continua fora do git de propósito (config local do Codex CLI).

---

## 3. Board de bugs — `TASK/items/`

O board estava **dividido em dois lugares**: `TASK/items/` do repo (versionado) e um board solto em `E:\Overclok\TASK\items` (fora de qualquer git, gerado pela rodada de QA das 17:24). **Foram consolidados aqui** — F-105/F-106/F-107/F-108/F-400 copiados para o repo, e a rodada de QA das 17:24 anexada ao fim de F-102, F-103 e F-104. O board solto foi apagado; `TASK/items/` do repo é a única fonte agora.

O apêndice de QA no fim do **F-103** vale a leitura: lista exatamente quais formas de query estouravam o timeout (sem params, `?limit=1`, `?state=SP`, `?sector=`, `?has_email=true`, `q` pouco seletivo). Como a verificação das 20:20 só exercitou `?limit=1`, essa lista é o roteiro do re-teste.

Ordem dos fatos do dia (importa para não ler status errado):
`12:13` board inicial → `17:24` rodada de QA reabre F-102/F-103 → **`20:20` dev corrige e verifica F-103/F-105 em produção** → `20:40–21:10` trabalho de frontend (Landing, api.ts).

| ID | Severidade | Status | Resumo |
| --- | --- | --- | --- |
| **F-103** | alta | **resolvido e verificado em prod (20:20)** | Causa real: `ORDER BY b.score DESC` com `WHERE TRUE` (sem `q`) forçava seq-scan + sort externo em 72M linhas e estourava o `command_timeout=30` do pool asyncpg. Correção: `ORDER BY b.score DESC` **só quando há `q`**; sem `q`, `ORDER BY b.cnpj` (btree da PK). Verificado: `/v1/search?limit=1` → **200 em 3740ms**, `/v1/company/00000000000191` → 200, `/v1/keys/me` → 200, `DELETE /v1/keys/me` → 204. 75/75 testes passando. |
| **F-105** | média | **corrigido (junto com F-103)** | `@app.exception_handler(Exception)` em `main.py` devolve `{"error":{"code":"internal_error","message":…,"status":500}}` em vez do texto puro do Starlette. Teste novo: `test_unhandled_errors.py`. |
| **F-106** | alta | **corrigido no código, falta verificar na UI** | `validateApiKey()` já **não** usa mais `/v1/search?limit=1`: agora chama `GET /v1/keys/me` (`frontend/src/lib/api.ts:90`). Esse código estava **fora do git até este commit** — confirmar se o que está servido em prod tem o fix. |
| **F-102** | alta | **corrigido no código, falta verificar na UI** | A UI travava em "Creating…" porque o bundle em prod lia `json.data.key` de um corpo achatado. `createFreeApiKey` já trata `res.status === 201` corretamente (`api.ts:119+`). O diagnóstico da QA foi **bundle velho em produção**, não código errado. → rebuild + redeploy do frontend e re-testar o fluxo completo pela UI. |
| **F-104** | média | **verificado** | `X-RateLimit-Limit/Remaining/Reset` presentes e corretos em respostas autenticadas de sucesso e no 204. Nada a fazer. |
| **F-107** | média | **aberto (pendência manual)** | O crash da F-102 acontecia **depois** do commit do 201 → a chave ficava ativa no banco e o valor se perdia (o endpoint só retorna uma vez). Limpeza pendente:<br>`UPDATE product.api_keys SET active=FALSE WHERE email='qa-testdata-20260906@ambern.dev';` |
| **F-108** | baixa | **precisa decisão do owner** | 403 `plan_forbidden` não carrega `X-RateLimit-*`. O contrato (linha 76) diz "toda resposta autenticada (sucesso e 429)" — ambíguo. Decidir se 403/401/404/422 também devem carregar. |
| **F-400** | baixa | **verificado** | `bbi-web` "Failed with result 'exit-code'" era artefato transitório do restart. Sem recorrência pós-redeploy. Fechado. |

Ponto em aberto que a auditoria levantou e **ninguém endereçou ainda**: o `ORDER BY` foi corrigido, mas o **`COUNT(*)` exato continua rodando antes da página de dados**. `COUNT(*) WHERE TRUE` custa ~315k e `COUNT(*) WHERE tem_divida = FALSE` faz parallel seq scan (~1,48M). Buscas amplas ainda podem ficar lentas por causa disso — é o próximo gargalo previsível.

---

## 4. Próximos passos sugeridos (ordem)

1. **Rebuild + redeploy do frontend** e re-verificar **F-102** e **F-106** pela UI (criar chave FREE → ver a chave → salvar → "✓ Key active"). É o desbloqueio de maior valor: o código já está certo, a dúvida é o que está servido.
2. **F-107** — rodar o `UPDATE` de desativação da chave órfã `qa-testdata-20260906@ambern.dev`.
3. **Contagem da busca** — implementar contagem limitada/opcional (ex.: `COUNT(*) … LIMIT n+1`, ou total aproximado com contrato de paginação honesto) antes de cogitar novos índices. A auditoria recomenda explicitamente **não** trocar o total exato por estimativa em silêncio.
4. **F-108** — decisão do owner.
5. Repassar a rodada de QA completa em `/v1/search` com filtros estruturais (`state`, `sector`, `has_email`) que a QA das 17:24 pegou em 500 — confirmar se o fix do `ORDER BY` cobriu todos, já que a verificação das 20:20 só exercitou `?limit=1`.

---

## 5. Como retomar na outra máquina

```bash
git clone https://github.com/amberndev/brazil-business-intelligence.git
cd brazil-business-intelligence

# backend
cd backend
cp .env.example .env        # preencher segredos (NÃO estão no git)
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q

# frontend
cd ../frontend
cp .env.example .env.local  # preencher
npm ci
npm run dev
```

Segredos (`backend/.env`, `frontend/.env.local`) **não vão pelo git** — copiar da máquina A ou do gerenciador de segredos.

Contexto adicional: `README.md`, `docs/CONTRACT.md`, `docs/qa-report.md`, `docs/qa-report-http-smoke.md`, `backend/SEARCH_DATASET_AUDIT.md`.
