# Search dataset contract and read-only audit

Verified on 2026-09-06 through SSH alias `worbita-dados`, using local PostgreSQL peer authentication (`sudo -n -u postgres psql -X -d worbita`). No credentials printed, no deployment or index changes.

## Supported filters and frontend coordination

- `status` omitted or `ATIVA`: searches active establishments in the dataset snapshot. `BAIXADA` and `SUSPENSA` now return HTTP 422 `unsupported_filter`, rather than silently returning active results. Invalid enum values still return `invalid_filter`. Frontend should label the scope “Empresas ativas” and remove/disable unsupported status choices. “Todas” must mean all active establishments, not all registry statuses.
- `has_debt=true` and `false` both filter `busca.tem_divida`; NULL matches neither. An omitted filter includes unknown flags. Results now preserve NULL (JSON null / empty CSV cell). Frontend must type this as `boolean | null` and display unknown separately, e.g. “Não informado”, rather than interpreting falsy values as no debt. False means no debt recorded by this dataset, not a debt clearance certificate.
- Name FTS, exact formatted/unformatted 14-digit CNPJ, accent-normalized municipality lookup, blank-aware email/primary-or-secondary-phone filters, existing ordering, and branch profile navigation remain intact.
- Existing size limitation: `MEDIO` and `GRANDE` both map to Receita porte 5; the dataset cannot distinguish them. Frontend should describe these as a combined “Demais empresas” category. MEI uses the independent `is_mei` flag.
- Status and debt are snapshot attributes; the search table is not a live registry check.

## Schema evidence

Read-only transaction with `SET LOCAL statement_timeout='5s'` queried `information_schema.columns`, `pg_indexes`, `pg_class`, and `pg_get_viewdef`.

`receita.busca` is a physical table (`relkind=r`), estimated 28,148,920 rows. 26 columns include `cnpj text NOT NULL`, `porte smallint`, `is_mei boolean`, `tem_divida boolean NULL`, `municipio integer`, contact fields and score. There is no status column. The ETL sources `/opt/worbita/etl/006-tabela-de-busca.sql:74` and `/opt/worbita/etl/022-rebuild-mensal.sql:116` explicitly restrict `e.situacao_cadastral = 2`. The latter sets `tem_divida` from `(dv.cnpj is not null)` at line 140. A bounded 1,000-row sample had 1,000 false debt flags; this is not a population distribution estimate.

Nine indexes: `busca_pkey`, `busca_nicho_cidade`, `busca_nicho_uf`, `busca_cnae_sec`, `busca_abertura`, `busca_municipio`, `busca_celular`, `busca_divida`, and `busca_nome_fts`. The debt index is partial `WHERE tem_divida`; the FTS expression matches the current router expression. No general debt-false index exists.

## Bounded performance evidence

All statements used a read-only transaction and 5-second statement timeout, followed by rollback. Broad counts were **EXPLAIN only**, never executed.

| Query | Observed plan/result |
| --- | --- |
| Broad `COUNT(*) WHERE TRUE` | Parallel Index Only Scan on `busca_abertura`; aggregate cost 315531.91..315531.92; scans the entire dataset |
| Broad page `ORDER BY b.cnpj LIMIT 20 OFFSET 0` | EXPLAIN ANALYZE: `busca_pkey` Index Scan, 20 rows, 24 shared-buffer hits, planning 2.290 ms, execution 1.674 ms |
| `COUNT(*) WHERE b.tem_divida = FALSE` | EXPLAIN only: Parallel Seq Scan; aggregate cost 1484370.89..1484370.90 |

The existing PK ordering fix is effective for the data page, but does not make the complete endpoint fast: its exact COUNT still runs first. Do not present the 1.674 ms page measurement as endpoint latency. Broad false-debt counts can be costly. A future reviewed performance change should consider bounded/optional counts with a truthful pagination contract before adding indexes; this audit does not change production indexes or silently replace exact totals with estimates.

## Regression validation

`python -m pytest tests/test_search.py tests/test_search_regressions.py tests/test_search_filter_contract.py -q` exercises existing CNPJ/name/contact/branch behavior, rejected statuses, debt true/false/NULL using executed SQL fixtures, count/data predicates, JSON and CSV unknown handling.
