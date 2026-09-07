"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { fetchSearch, getStoredApiKey } from "@/lib/api";
import type { SearchResultRow, Pagination } from "@/lib/api-types";

const STATES = [
  "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG",
  "PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO",
];
const SIZES = ["MEI", "ME", "EPP", "MEDIO", "GRANDE"] as const;
const STATUSES = ["ATIVA", "BAIXADA", "SUSPENSA"] as const;

type Filters = {
  q: string;
  city: string;
  has_email: boolean | "";
  has_phone: boolean | "";
  state: string;
  sector: string;
  size: string;
  status: string;
  has_debt: boolean | "";
  page: number;
};

const DEFAULT_FILTERS: Filters = {
  q: "",
  city: "",
  has_email: "",
  has_phone: "",
  state: "",
  sector: "",
  size: "",
  status: "",
  has_debt: "",
  page: 1,
};

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "ATIVA"
      ? { bg: "rgba(22,163,74,0.1)", text: "#15803d", border: "#16a34a" }
      : status === "BAIXADA"
      ? { bg: "rgba(220,38,38,0.1)", text: "#b91c1c", border: "#dc2626" }
      : { bg: "rgba(180,83,9,0.1)", text: "#92400e", border: "#b45309" };
  return (
    <span
      style={{
        fontSize: "0.7rem",
        fontWeight: 600,
        padding: "0.15rem 0.5rem",
        borderRadius: "99px",
        background: color.bg,
        color: color.text,
        border: `1px solid ${color.border}`,
        whiteSpace: "nowrap",
      }}
    >
      {status}
    </span>
  );
}

function DebtBadge({ hasDebt }: { hasDebt: boolean }) {
  if (!hasDebt) return null;
  return (
    <span
      style={{
        fontSize: "0.7rem",
        fontWeight: 600,
        padding: "0.15rem 0.5rem",
        borderRadius: "99px",
        background: "rgba(220,38,38,0.1)",
        color: "#b91c1c",
        border: "1px solid #dc2626",
        whiteSpace: "nowrap",
      }}
    >
      PGFN Debt
    </span>
  );
}

export default function SearchPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const applied = useRef(DEFAULT_FILTERS);
  const request = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const [results, setResults] = useState<SearchResultRow[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [noKey, setNoKey] = useState(false);

  useEffect(() => {
    document.title = "Search — Brazil Business Intelligence";
  }, []);

  async function runSearch(f: Filters) {
    if (!getStoredApiKey()) { setNoKey(true); return; }
    setNoKey(false);
    const id = ++request.current;
    controller.current?.abort();
    controller.current = new AbortController();
    applied.current = { ...f };
    setLoading(true);
    setError(null);

    const params: Record<string, string | number | boolean> = { page: f.page, limit: 20 };
    const query = f.q.trim();
    if (query) params.q = /^[\d.\/\s-]+$/.test(query) ? query.replace(/\D/g, "") : query;
    if (f.city.trim()) params.city = f.city.trim();
    if (f.has_email !== "") params.has_email = f.has_email;
    if (f.has_phone !== "") params.has_phone = f.has_phone;
    if (f.state) params.state = f.state;
    if (f.sector) params.sector = f.sector;
    if (f.size) params.size = f.size;
    if (f.status) params.status = f.status;
    if (f.has_debt !== "") params.has_debt = f.has_debt as boolean;

    const result = await fetchSearch(params, controller.current.signal);
    if (id !== request.current) return;
    setLoading(false);
    if (result.ok) {
      setResults(result.data.results);
      setPagination(result.data.pagination);
    } else {
      setError(result.error.message);
      setResults([]);
      setPagination(null);
    }
  }
  useEffect(() => {
    setNoKey(!getStoredApiKey());
    return () => { ++request.current; controller.current?.abort(); };
  }, []);

  function setFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((f) => ({ ...f, [key]: value, page: key === "page" ? (value as number) : 1 }));
  }

  return (
    <form className="company-search-layout" onSubmit={(e) => { e.preventDefault(); void runSearch({ ...filters, page: 1 }); }} style={{ display: "flex", minHeight: "calc(100vh - 130px)" }}>
      {/* Filters sidebar */}
      <aside
        id="search-filters"
        style={{
          width: "240px",
          flexShrink: 0,
          borderRight: "1px solid var(--border)",
          padding: "1.5rem 1.25rem",
          display: "flex",
          flexDirection: "column",
          gap: "1.25rem",
        }}
      >
        <h2 style={{ fontSize: "0.875rem", fontWeight: 700, margin: 0, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Filters
        </h2>

        {/* State */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
          <label style={{ fontSize: "0.75rem", fontWeight: 500, color: "var(--muted)" }}>State (UF)</label>
          <select
            value={filters.state}
            onChange={(e) => setFilter("state", e.target.value)}
            style={selectStyle}
          >
            <option value="">All states</option>
            {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <label style={{ fontSize: "0.8rem" }}>City
          <input value={filters.city} onChange={(e) => setFilter("city", e.target.value)} placeholder="City name" style={inputStyle} />
        </label>
        {(["has_email", "has_phone"] as const).map((field) => (
          <label key={field} style={{ display: "flex", gap: "0.5rem", fontSize: "0.8rem" }}>
            <input type="checkbox" checked={filters[field] === true} onChange={(e) => setFilter(field, e.target.checked ? true : "")} />
            {field === "has_email" ? "Has email" : "Has phone"}
          </label>
        ))}
        {/* Sector */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
          <label style={{ fontSize: "0.75rem", fontWeight: 500, color: "var(--muted)" }}>Sector (CNAE)</label>
          <input
            type="text"
            value={filters.sector}
            onChange={(e) => setFilter("sector", e.target.value)}
            placeholder="e.g. 6201"
            style={inputStyle}
          />
        </div>

        {/* Size */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
          <label style={{ fontSize: "0.75rem", fontWeight: 500, color: "var(--muted)" }}>Size</label>
          <select
            value={filters.size}
            onChange={(e) => setFilter("size", e.target.value)}
            style={selectStyle}
          >
            <option value="">All sizes</option>
            {SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        {/* Status */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
          <label style={{ fontSize: "0.75rem", fontWeight: 500, color: "var(--muted)" }}>Status</label>
          <select
            value={filters.status}
            onChange={(e) => setFilter("status", e.target.value)}
            style={selectStyle}
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        {/* Has debt */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <input
            type="checkbox"
            id="filter-has-debt"
            checked={filters.has_debt === true}
            onChange={(e) => setFilter("has_debt", e.target.checked ? true : "")}
            style={{ width: "16px", height: "16px", cursor: "pointer" }}
          />
          <label htmlFor="filter-has-debt" style={{ fontSize: "0.8rem", cursor: "pointer" }}>
            Has PGFN debt only
          </label>
        </div>

        <button
          type="button" onClick={() => setFilters(DEFAULT_FILTERS)}
          style={{
            background: "transparent",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            padding: "0.4rem 0.75rem",
            fontSize: "0.8rem",
            cursor: "pointer",
            color: "var(--muted)",
          }}
        >
          Clear filters
        </button>
      </aside>

      {/* Main content */}
      <div style={{ flex: 1, padding: "1.5rem", minWidth: 0 }}>
        {/* Search input */}
        <label htmlFor="search-input">Company name or CNPJ</label>
        <div style={{ marginBottom: "1.25rem" }}>
          <input
            id="search-input"
            type="search"
            value={filters.q}
            onChange={(e) => setFilter("q", e.target.value)}
            placeholder="Company name or 00.000.000/0170-86"
            aria-describedby="search-help"
            style={{
              ...inputStyle,
              width: "100%",
              fontSize: "1rem",
              padding: "0.65rem 1rem",
            }}
          />
        </div>

        <p id="search-help" style={{ color: "var(--muted)", fontSize: "0.8rem" }}>Search by name or CNPJ with or without punctuation. Press Search to apply your filters.</p>
        <button type="submit" style={{ ...paginationBtnStyle(false), background: "var(--accent)", color: "var(--accent-foreground, #fff)", marginBottom: "1rem", padding: "0.65rem 1.25rem" }}>Search</button>
        {/* No-key inline prompt (within the page shell — landmarks still render) */}
        {noKey && (
          <div
            style={{
              border: "1px solid var(--border)",
              borderRadius: "8px",
              padding: "1rem 1.25rem",
              background: "var(--card)",
              marginBottom: "1rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "1rem",
              flexWrap: "wrap",
            }}
          >
            <span style={{ fontSize: "0.875rem", color: "var(--muted)" }}>
              Enter your API key to run searches.
            </span>
            <Link
              href="/app/keys"
              style={{
                background: "var(--accent)",
                color: "#fff",
                padding: "0.4rem 1rem",
                borderRadius: "6px",
                textDecoration: "none",
                fontWeight: 600,
                fontSize: "0.875rem",
                whiteSpace: "nowrap",
              }}
            >
              Enter API Key
            </Link>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div role="alert"
            style={{
              border: "1px solid #dc2626",
              borderRadius: "8px",
              padding: "1rem",
              background: "rgba(220,38,38,0.05)",
              color: "#b91c1c",
              marginBottom: "1rem",
            }}
          >
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>Searching…</p>
        )}

        {/* Results table — ALWAYS rendered so CONTRACT landmark #results-table exists pre-auth */}
        <div style={{ overflowX: "auto" }}>
          <table
            id="results-table"
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "0.875rem",
            }}
          >
            <thead>
              <tr style={{ borderBottom: "2px solid var(--border)" }}>
                {["CNPJ", "Name", "City / UF", "Sector", "Status", "Debt"].map((h) => (
                  <th
                    key={h}
                    style={{
                      padding: "0.5rem 0.75rem",
                      textAlign: "left",
                      fontWeight: 600,
                      fontSize: "0.75rem",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                      color: "var(--muted)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.map((row) => (
                <tr
                  key={row.cnpj}
                  style={{ borderBottom: "1px solid var(--border)" }}
                >
                  <td style={tdStyle}>
                    <Link
                      href={`/app/company/${row.cnpj}`}
                      style={{ color: "var(--accent)", textDecoration: "none", fontFamily: "monospace", fontSize: "0.8rem" }}
                    >
                      {row.cnpj_formatted}
                    </Link>
                  </td>
                  <td style={{ ...tdStyle, maxWidth: "220px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <Link
                      href={`/app/company/${row.cnpj}`}
                      style={{ color: "inherit", textDecoration: "none" }}
                    >
                      {row.name}
                    </Link>
                  </td>
                  <td style={tdStyle}>
                    {row.city && row.state ? `${row.city}, ${row.state}` : row.state ?? row.city ?? "—"}
                  </td>
                  <td style={{ ...tdStyle, maxWidth: "180px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--muted)" }}>
                    {row.sector ?? "—"}
                  </td>
                  <td style={tdStyle}>
                    <StatusBadge status={row.status} />
                  </td>
                  <td style={tdStyle}>
                    <DebtBadge hasDebt={row.has_debt} />
                  </td>
                </tr>
              ))}
              {results.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} style={{ ...tdStyle, color: "var(--muted)", textAlign: "center", padding: "2rem" }}>
                    {noKey
                      ? "Enter an API key to search 72M+ Brazilian companies."
                      : pagination !== null
                      ? "No companies found. Try adjusting your filters."
                      : "Start searching to see results."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination — ALWAYS rendered so CONTRACT landmark #results-pagination exists pre-auth */}
        <div
          id="results-pagination"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: "1.25rem",
            fontSize: "0.875rem",
          }}
        >
          <p style={{ color: "var(--muted)", margin: 0 }}>
            {pagination
              ? `${pagination.total.toLocaleString()} companies found — page ${pagination.page} of ${pagination.total_pages}`
              : " "}
          </p>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="button" onClick={() => pagination && runSearch({ ...applied.current, page: pagination.page - 1 })}
              disabled={loading || !pagination || pagination.page <= 1}
              style={paginationBtnStyle(loading || !pagination || pagination.page <= 1)}
            >
              ← Previous
            </button>
            <button
              type="button" onClick={() => pagination && runSearch({ ...applied.current, page: pagination.page + 1 })}
              disabled={loading || !pagination || pagination.page >= pagination.total_pages}
              style={paginationBtnStyle(loading || !pagination || pagination.page >= pagination.total_pages)}
            >
              Next →
            </button>
          </div>
        </div>
      </div>
    </form>
  );
}

const inputStyle: React.CSSProperties = {
  border: "1.5px solid var(--border)",
  borderRadius: "6px",
  padding: "0.4rem 0.7rem",
  fontSize: "0.875rem",
  background: "var(--background)",
  color: "var(--foreground)",
  outline: "none",
  width: "100%",
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  cursor: "pointer",
};

const tdStyle: React.CSSProperties = {
  padding: "0.6rem 0.75rem",
  verticalAlign: "middle",
};

function paginationBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    border: "1px solid var(--border)",
    borderRadius: "6px",
    padding: "0.35rem 0.75rem",
    fontSize: "0.8rem",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.4 : 1,
    background: "var(--card)",
    color: "var(--foreground)",
  };
}
