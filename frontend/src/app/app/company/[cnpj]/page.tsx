"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  fetchCompanyProfile,
  fetchCompanyCompliance,
  fetchCompanyShareholders,
  getStoredApiKey,
} from "@/lib/api";
import type {
  CompanyProfile,
  CompanyCompliance,
  CompanyShareholders,
} from "@/lib/api-types";

type LoadState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; data: T }
  | { status: "error"; message: string; code?: string };

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
        display: "inline-block",
        fontSize: "0.75rem",
        fontWeight: 700,
        padding: "0.25rem 0.75rem",
        borderRadius: "99px",
        background: color.bg,
        color: color.text,
        border: `1px solid ${color.border}`,
      }}
    >
      {status}
    </span>
  );
}

function SectionCard({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section
      id={id}
      style={{
        border: "1px solid var(--border)",
        borderRadius: "10px",
        padding: "1.5rem",
        background: "var(--card)",
      }}
    >
      <h2
        style={{
          fontSize: "0.8rem",
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--muted)",
          margin: "0 0 1rem",
        }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "160px 1fr",
        gap: "0.5rem",
        padding: "0.4rem 0",
        borderBottom: "1px solid var(--border)",
        fontSize: "0.875rem",
      }}
    >
      <span style={{ color: "var(--muted)", fontWeight: 500 }}>{label}</span>
      <span style={{ wordBreak: "break-word" }}>{value ?? "—"}</span>
    </div>
  );
}

function formatBRL(n: number): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(n);
}

export default function CompanyPage() {
  const params = useParams();
  const cnpj = Array.isArray(params.cnpj) ? params.cnpj[0] : params.cnpj ?? "";

  const [noKey, setNoKey] = useState(false);
  const [profile, setProfile] = useState<LoadState<CompanyProfile>>({ status: "loading" });
  const [compliance, setCompliance] = useState<LoadState<CompanyCompliance>>({ status: "loading" });
  const [shareholders, setShareholders] = useState<LoadState<CompanyShareholders>>({ status: "loading" });

  useEffect(() => {
    if (!cnpj) return;
    document.title = `Company — Brazil Business Intelligence`;

    // Gate only the DATA FETCH behind the key — the landmark shell always renders below.
    if (!getStoredApiKey()) {
      setNoKey(true);
      setProfile({ status: "idle" });
      setCompliance({ status: "idle" });
      setShareholders({ status: "idle" });
      return;
    }

    // Fetch all three in parallel
    fetchCompanyProfile(cnpj).then((r) => {
      if (r.ok) {
        setProfile({ status: "ok", data: r.data });
        document.title = `${r.data.razao_social} — Brazil Business Intelligence`;
      } else {
        setProfile({ status: "error", message: r.error.message, code: r.error.code });
      }
    });

    fetchCompanyCompliance(cnpj).then((r) => {
      if (r.ok) {
        setCompliance({ status: "ok", data: r.data });
      } else {
        setCompliance({ status: "error", message: r.error.message, code: r.error.code });
      }
    });

    fetchCompanyShareholders(cnpj).then((r) => {
      if (r.ok) {
        setShareholders({ status: "ok", data: r.data });
      } else {
        setShareholders({ status: "error", message: r.error.message, code: r.error.code });
      }
    });
  }, [cnpj]);

  const p = profile.status === "ok" ? profile.data : null;
  const isNotFound = profile.status === "error" && profile.code === "not_found";

  // Shown inside profile-backed sections when there is no profile data yet.
  const profileNote: React.ReactNode = noKey ? (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
      <span style={{ color: "var(--muted)", fontSize: "0.875rem" }}>
        Enter your API key to load this company.
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
  ) : profile.status === "loading" ? (
    <p style={{ color: "var(--muted)", fontSize: "0.875rem", margin: 0 }}>Loading…</p>
  ) : profile.status === "error" ? (
    <p style={{ color: "var(--muted)", fontSize: "0.875rem", margin: 0 }}>
      {isNotFound ? "Company not found." : profile.message}
    </p>
  ) : null;

  return (
    <div style={{ maxWidth: "900px", margin: "2rem auto", padding: "0 1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      {/* Back link */}
      <Link href="/app/search" style={{ color: "var(--muted)", fontSize: "0.875rem", textDecoration: "none" }}>
        ← Search results
      </Link>

      {/* Header — always rendered; shows company name when loaded, else a title + status note */}
      <section id="company-header" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
          <h1
            style={{
              fontSize: "clamp(1.25rem, 3vw, 1.75rem)",
              fontWeight: 800,
              margin: 0,
              letterSpacing: "-0.02em",
            }}
          >
            {p ? p.razao_social : "Company Profile"}
          </h1>
          {p && <StatusBadge status={p.status} />}
        </div>
        {p?.nome_fantasia && (
          <p style={{ color: "var(--muted)", margin: 0, fontSize: "1rem" }}>
            {p.nome_fantasia}
          </p>
        )}
        <p style={{ color: "var(--muted)", fontSize: "0.875rem", fontFamily: "monospace", margin: 0 }}>
          {p ? p.cnpj_formatted : cnpj}
        </p>
        {!p && profileNote}
      </section>

      {/* Overview */}
      <SectionCard id="company-overview" title="Overview">
        {p ? (
          <>
            <InfoRow label="Legal Nature" value={p.legal_nature} />
            <InfoRow label="Size" value={p.size} />
            <InfoRow
              label="Share Capital"
              value={p.share_capital != null ? formatBRL(p.share_capital) : null}
            />
            <InfoRow
              label="Opened"
              value={p.opened_at ? new Date(p.opened_at).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }) : null}
            />
          </>
        ) : (
          profileNote
        )}
      </SectionCard>

      {/* Location */}
      <SectionCard id="company-location" title="Location">
        {p ? (
          <>
            <InfoRow
              label="Address"
              value={[p.location.street, p.location.number, p.location.complement].filter(Boolean).join(", ") || null}
            />
            <InfoRow label="District" value={p.location.district} />
            <InfoRow
              label="City / State"
              value={[p.location.city, p.location.state].filter(Boolean).join(", ") || null}
            />
            <InfoRow label="ZIP (CEP)" value={p.location.zip} />
          </>
        ) : (
          profileNote
        )}
      </SectionCard>

      {/* Sector */}
      <SectionCard id="company-sector" title="Sector">
        {p ? (
          <>
            {p.sector.primary_cnae ? (
              <InfoRow
                label="Primary CNAE"
                value={`${p.sector.primary_cnae.code} — ${p.sector.primary_cnae.description ?? "—"}`}
              />
            ) : (
              <InfoRow label="Primary CNAE" value={null} />
            )}
            {p.sector.secondary_cnae.length > 0 && (
              <div style={{ paddingTop: "0.5rem" }}>
                <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 0.5rem" }}>
                  Secondary CNAEs ({p.sector.secondary_cnae.length})
                </p>
                {p.sector.secondary_cnae.slice(0, 5).map((c) => (
                  <div key={c.code} style={{ fontSize: "0.8rem", padding: "0.2rem 0", color: "var(--muted)" }}>
                    {c.code} — {c.description ?? "—"}
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          profileNote
        )}
      </SectionCard>

      {/* Contact */}
      <SectionCard id="company-contact" title="Contact">
        {p ? (
          <>
            <InfoRow label="Phone" value={p.contact.phone} />
            <InfoRow
              label="Email"
              value={
                p.contact.email ? (
                  <a href={`mailto:${p.contact.email}`} style={{ color: "var(--accent)" }}>
                    {p.contact.email}
                  </a>
                ) : null
              }
            />
          </>
        ) : (
          profileNote
        )}
      </SectionCard>

      {/* Compliance */}
      <SectionCard id="company-compliance" title="Compliance">
        {compliance.status === "idle" && profileNote}
        {compliance.status === "loading" && (
          <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>Loading compliance data…</p>
        )}
        {compliance.status === "error" && (
          <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>
            {compliance.code === "plan_forbidden"
              ? "Compliance data requires STARTER plan or above."
              : compliance.message}
          </p>
        )}
        {compliance.status === "ok" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {/* PGFN */}
            <div>
              <p style={{ fontWeight: 600, fontSize: "0.875rem", margin: "0 0 0.5rem" }}>PGFN Federal Debt</p>
              <InfoRow
                label="Has debt"
                value={
                  compliance.data.pgfn_debt.has_debt ? (
                    <span style={{ color: "#dc2626", fontWeight: 600 }}>Yes</span>
                  ) : (
                    <span style={{ color: "#16a34a", fontWeight: 600 }}>No</span>
                  )
                }
              />
              {compliance.data.pgfn_debt.has_debt && (
                <>
                  <InfoRow label="Total amount" value={formatBRL(compliance.data.pgfn_debt.total_amount)} />
                  <InfoRow label="Records" value={compliance.data.pgfn_debt.records_count} />
                </>
              )}
            </div>
            {/* CGU */}
            <div>
              <p style={{ fontWeight: 600, fontSize: "0.875rem", margin: "0 0 0.5rem" }}>CGU Sanctions</p>
              <InfoRow
                label="Has sanctions"
                value={
                  compliance.data.cgu_sanctions.has_sanctions ? (
                    <span style={{ color: "#dc2626", fontWeight: 600 }}>Yes ({compliance.data.cgu_sanctions.count})</span>
                  ) : (
                    <span style={{ color: "#16a34a", fontWeight: 600 }}>No</span>
                  )
                }
              />
              {compliance.data.cgu_sanctions.items.length > 0 && (
                <div style={{ marginTop: "0.5rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {compliance.data.cgu_sanctions.items.map((item, i) => (
                    <div
                      key={i}
                      style={{
                        border: "1px solid var(--border)",
                        borderRadius: "6px",
                        padding: "0.75rem",
                        fontSize: "0.8rem",
                      }}
                    >
                      <p style={{ fontWeight: 600, margin: "0 0 0.25rem" }}>{item.type}</p>
                      {item.description && <p style={{ color: "var(--muted)", margin: "0 0 0.25rem" }}>{item.description}</p>}
                      {item.start_date && (
                        <p style={{ color: "var(--muted)", margin: 0 }}>
                          {item.start_date} — {item.end_date ?? "ongoing"}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </SectionCard>

      {/* Shareholders */}
      <SectionCard id="company-shareholders" title="Shareholders & Partners">
        {shareholders.status === "idle" && profileNote}
        {shareholders.status === "loading" && (
          <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>Loading shareholder data…</p>
        )}
        {shareholders.status === "error" && (
          <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>
            {shareholders.code === "plan_forbidden"
              ? "Shareholder data requires STARTER plan or above."
              : shareholders.message}
          </p>
        )}
        {shareholders.status === "ok" && shareholders.data.count === 0 && (
          <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>No shareholder records found.</p>
        )}
        {shareholders.status === "ok" && shareholders.data.count > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--border)" }}>
                  {["Name", "Document", "Role", "Participation %", "Since"].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: "0.4rem 0.75rem",
                        textAlign: "left",
                        fontSize: "0.75rem",
                        fontWeight: 600,
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
                {shareholders.data.shareholders.map((sh, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "0.5rem 0.75rem", fontWeight: 500 }}>{sh.name}</td>
                    <td style={{ padding: "0.5rem 0.75rem", fontFamily: "monospace", fontSize: "0.8rem", color: "var(--muted)" }}>
                      {sh.document ?? "—"}
                    </td>
                    <td style={{ padding: "0.5rem 0.75rem", color: "var(--muted)" }}>{sh.role ?? "—"}</td>
                    <td style={{ padding: "0.5rem 0.75rem", fontWeight: 600 }}>
                      {sh.participation_pct != null ? `${sh.participation_pct.toFixed(2)}%` : "—"}
                    </td>
                    <td style={{ padding: "0.5rem 0.75rem", color: "var(--muted)" }}>{sh.since ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
