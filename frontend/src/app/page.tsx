import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Verify Any Brazilian Company in Milliseconds",
};

const STATS = [
  { value: "72M+", label: "Companies" },
  { value: "28M", label: "Active Entities" },
  { value: "6.8M", label: "With PGFN Debt" },
  { value: "Updated Monthly", label: "Data Refresh" },
];

const USE_CASES = [
  {
    title: "Due Diligence",
    description:
      "Instantly verify any Brazilian company before signing contracts, investing, or onboarding. Check status, shareholders, and compliance in one call.",
    icon: "🔍",
  },
  {
    title: "Market Entry",
    description:
      "Explore 72M+ companies by state, sector, and size. Identify distributors, partners, and competitors with a single filtered search.",
    icon: "🗺️",
  },
  {
    title: "Compliance",
    description:
      "Screen entities against PGFN federal debt and CGU sanctions databases. Get structured sanction records with date ranges and categories.",
    icon: "🛡️",
  },
];

const PLANS = [
  {
    name: "Free",
    price: "$0",
    quota: "50 req/mo",
    features: ["CNPJ Lookup", "Basic Search"],
    cta: "Get Free Key",
    ctaHref: "/app/keys",
    highlight: false,
  },
  {
    name: "Starter",
    price: "$79",
    quota: "2,000 req/mo",
    features: ["Everything in Free", "Compliance Data", "Shareholders", "Batch Lookup"],
    cta: "Get Starter",
    ctaHref: "/app/keys",
    highlight: false,
  },
  {
    name: "Pro",
    price: "$249",
    quota: "15,000 req/mo",
    features: ["Everything in Starter", "CSV Export", "Market Overview", "Email Support"],
    cta: "Contact Sales",
    ctaHref: `mailto:${process.env.CONTACT_EMAIL ?? "vinicius@ambern.dev"}?subject=Pro Plan`,
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    quota: "Unlimited",
    features: ["Everything in Pro", "SLA", "IP Whitelist", "Dedicated Support"],
    cta: "Contact Sales",
    ctaHref: `mailto:${process.env.CONTACT_EMAIL ?? "vinicius@ambern.dev"}?subject=Enterprise Plan`,
    highlight: false,
  },
];

const REQUEST_EXAMPLE = `curl https://brazil.ambern.dev/v1/company/12345678000195 \\
  -H "X-API-Key: bbi_your_key_here"`;

const RESPONSE_EXAMPLE = `{
  "data": {
    "cnpj": "12345678000195",
    "cnpj_formatted": "12.345.678/0001-95",
    "razao_social": "EMPRESA EXEMPLO LTDA",
    "nome_fantasia": "Empresa Exemplo",
    "status": "ATIVA",
    "size": "ME",
    "location": {
      "city": "São Paulo",
      "state": "SP"
    },
    "sector": {
      "primary_cnae": {
        "code": "6201-5/00",
        "description": "Software development"
      }
    }
  },
  "meta": {
    "query_time_ms": 0.42,
    "plan": "STARTER",
    "requests_remaining": 1847
  }
}`;

export default function LandingPage() {
  return (
    <div>
      {/* Hero */}
      <section
        id="hero"
        style={{
          padding: "6rem 2rem 5rem",
          maxWidth: "960px",
          margin: "0 auto",
          textAlign: "center",
        }}
      >
        <p
          style={{
            fontSize: "0.8rem",
            fontWeight: 600,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--accent)",
            marginBottom: "1.25rem",
          }}
        >
          Brazilian Company Intelligence API
        </p>
        <h1
          style={{
            fontSize: "clamp(2rem, 5vw, 3.5rem)",
            fontWeight: 800,
            lineHeight: 1.1,
            marginBottom: "1.5rem",
            letterSpacing: "-0.03em",
          }}
        >
          Verify Any Brazilian Company{" "}
          <span style={{ color: "var(--accent)" }}>in Milliseconds</span>
        </h1>
        <p
          style={{
            fontSize: "1.15rem",
            color: "var(--muted)",
            maxWidth: "600px",
            margin: "0 auto 2.5rem",
          }}
        >
          Access 72M+ companies, PGFN federal debt, CGU sanctions, shareholders,
          and market data through a single REST API. Start free, no credit card
          required.
        </p>
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
          <Link
            id="cta-get-key"
            href="/app/keys"
            style={{
              background: "var(--accent)",
              color: "#fff",
              padding: "0.75rem 1.75rem",
              borderRadius: "8px",
              textDecoration: "none",
              fontWeight: 700,
              fontSize: "1rem",
              display: "inline-block",
            }}
          >
            Get API Key — Free
          </Link>
          <Link
            id="cta-view-docs"
            href="/docs"
            style={{
              border: "1.5px solid var(--border)",
              color: "var(--foreground)",
              padding: "0.75rem 1.75rem",
              borderRadius: "8px",
              textDecoration: "none",
              fontWeight: 600,
              fontSize: "1rem",
              display: "inline-block",
            }}
          >
            View Docs
          </Link>
        </div>
      </section>

      {/* Stats bar */}
      <section
        id="stats-bar"
        style={{
          background: "var(--card)",
          borderTop: "1px solid var(--border)",
          borderBottom: "1px solid var(--border)",
          padding: "2rem",
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: "1.5rem",
            maxWidth: "960px",
            margin: "0 auto",
            textAlign: "center",
          }}
        >
          {STATS.map((s) => (
            <div key={s.label}>
              <p
                style={{
                  fontSize: "1.75rem",
                  fontWeight: 800,
                  margin: 0,
                  color: "var(--accent)",
                }}
              >
                {s.value}
              </p>
              <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.875rem" }}>
                {s.label}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Use cases */}
      <section
        id="use-cases"
        style={{ padding: "5rem 2rem", maxWidth: "960px", margin: "0 auto" }}
      >
        <h2
          style={{
            fontSize: "2rem",
            fontWeight: 700,
            textAlign: "center",
            marginBottom: "3rem",
            letterSpacing: "-0.02em",
          }}
        >
          Built for Real Workflows
        </h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: "1.5rem",
          }}
        >
          {USE_CASES.map((uc) => (
            <div
              key={uc.title}
              style={{
                border: "1px solid var(--border)",
                borderRadius: "12px",
                padding: "1.75rem",
                background: "var(--card)",
              }}
            >
              <div style={{ fontSize: "2rem", marginBottom: "0.75rem" }}>{uc.icon}</div>
              <h3 style={{ fontWeight: 700, fontSize: "1.1rem", marginBottom: "0.5rem" }}>
                {uc.title}
              </h3>
              <p style={{ color: "var(--muted)", fontSize: "0.9rem", lineHeight: 1.6, margin: 0 }}>
                {uc.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* API preview */}
      <section
        id="api-preview"
        style={{
          background: "var(--card)",
          borderTop: "1px solid var(--border)",
          borderBottom: "1px solid var(--border)",
          padding: "5rem 2rem",
        }}
      >
        <div style={{ maxWidth: "960px", margin: "0 auto" }}>
          <h2
            style={{
              fontSize: "2rem",
              fontWeight: 700,
              marginBottom: "0.75rem",
              letterSpacing: "-0.02em",
            }}
          >
            Simple, Predictable API
          </h2>
          <p style={{ color: "var(--muted)", marginBottom: "2rem" }}>
            RESTful endpoints with consistent JSON envelopes. One header, instant data.
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              gap: "1.5rem",
            }}
          >
            <div>
              <p
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "var(--muted)",
                  marginBottom: "0.5rem",
                }}
              >
                Request
              </p>
              <pre
                style={{
                  background: "#0f172a",
                  color: "#e2e8f0",
                  padding: "1.25rem",
                  borderRadius: "8px",
                  overflowX: "auto",
                  fontSize: "0.8rem",
                  lineHeight: 1.7,
                  margin: 0,
                }}
              >
                <code>{REQUEST_EXAMPLE}</code>
              </pre>
            </div>
            <div>
              <p
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "var(--muted)",
                  marginBottom: "0.5rem",
                }}
              >
                Response
              </p>
              <pre
                style={{
                  background: "#0f172a",
                  color: "#e2e8f0",
                  padding: "1.25rem",
                  borderRadius: "8px",
                  overflowX: "auto",
                  fontSize: "0.8rem",
                  lineHeight: 1.7,
                  margin: 0,
                }}
              >
                <code>{RESPONSE_EXAMPLE}</code>
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section
        id="pricing"
        style={{ padding: "5rem 2rem", maxWidth: "1100px", margin: "0 auto" }}
      >
        <h2
          style={{
            fontSize: "2rem",
            fontWeight: 700,
            textAlign: "center",
            marginBottom: "0.75rem",
            letterSpacing: "-0.02em",
          }}
        >
          Transparent Pricing
        </h2>
        <p
          style={{
            textAlign: "center",
            color: "var(--muted)",
            marginBottom: "3rem",
          }}
        >
          Free to start. Scale as you grow. No hidden fees.
        </p>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "1.25rem",
          }}
        >
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              style={{
                border: plan.highlight
                  ? "2px solid var(--accent)"
                  : "1px solid var(--border)",
                borderRadius: "12px",
                padding: "1.75rem",
                background: plan.highlight ? "var(--accent)" : "var(--card)",
                color: plan.highlight ? "#fff" : "inherit",
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
              }}
            >
              <div>
                <p
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    margin: 0,
                    opacity: 0.7,
                  }}
                >
                  {plan.name}
                </p>
                <p
                  style={{
                    fontSize: "2rem",
                    fontWeight: 800,
                    margin: "0.25rem 0 0",
                    letterSpacing: "-0.02em",
                  }}
                >
                  {plan.price}
                  {plan.price !== "Custom" && (
                    <span style={{ fontSize: "1rem", fontWeight: 400, opacity: 0.7 }}>
                      /mo
                    </span>
                  )}
                </p>
                <p style={{ fontSize: "0.8rem", opacity: 0.7, margin: "0.25rem 0 0" }}>
                  {plan.quota}
                </p>
              </div>
              <ul
                style={{
                  listStyle: "none",
                  padding: 0,
                  margin: "0.5rem 0",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                  flex: 1,
                }}
              >
                {plan.features.map((f) => (
                  <li key={f} style={{ display: "flex", gap: "0.5rem", fontSize: "0.875rem" }}>
                    <span style={{ opacity: 0.7 }}>✓</span>
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                href={plan.ctaHref}
                style={{
                  display: "block",
                  textAlign: "center",
                  padding: "0.6rem 1rem",
                  borderRadius: "6px",
                  textDecoration: "none",
                  fontWeight: 600,
                  fontSize: "0.875rem",
                  background: plan.highlight ? "rgba(255,255,255,0.2)" : "var(--accent)",
                  color: plan.highlight ? "#fff" : "#fff",
                  border: plan.highlight ? "1px solid rgba(255,255,255,0.3)" : "none",
                }}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
