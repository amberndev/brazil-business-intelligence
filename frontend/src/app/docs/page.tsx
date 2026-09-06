"use client";

import { useEffect, useRef } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100";
// Backend serves the OpenAPI schema at /openapi.json (NO /v1 prefix).
// Prod chain: NEXT_PUBLIC_API_URL=https://brazil.ambern.dev/api; Caddy handle_path strips /api.
const OPENAPI_URL = `${API_BASE}/openapi.json`;

export default function DocsPage() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.title = "API Docs — Brazil Business Intelligence";

    // Load Redoc standalone bundle
    const script = document.createElement("script");
    script.src =
      "https://cdn.jsdelivr.net/npm/redoc@2.2.0/bundles/redoc.standalone.js";
    script.async = true;
    script.onload = () => {
      if (containerRef.current && (window as typeof window & { Redoc?: { init: (url: string, opts: object, el: HTMLElement) => void } }).Redoc) {
        (window as typeof window & { Redoc: { init: (url: string, opts: object, el: HTMLElement) => void } }).Redoc.init(
          OPENAPI_URL,
          {
            scrollYOffset: 60,
            hideDownloadButton: false,
            theme: {
              colors: { primary: { main: "#1d4ed8" } },
              typography: {
                fontFamily: "system-ui, -apple-system, sans-serif",
                fontSize: "15px",
              },
            },
          },
          containerRef.current
        );
      }
    };
    document.body.appendChild(script);

    return () => {
      if (script.parentNode) script.parentNode.removeChild(script);
    };
  }, []);

  return (
    <main id="api-docs" style={{ minHeight: "80vh" }}>
      {/* English quickstart */}
      <div
        style={{
          maxWidth: "900px",
          margin: "0 auto",
          padding: "2.5rem 2rem 1rem",
        }}
      >
        <h1
          style={{
            fontSize: "1.75rem",
            fontWeight: 700,
            marginBottom: "0.5rem",
            letterSpacing: "-0.02em",
          }}
        >
          API Reference
        </h1>
        <p style={{ color: "var(--muted)", marginBottom: "1.5rem" }}>
          Base URL:{" "}
          <code
            style={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              padding: "0.1rem 0.4rem",
              fontFamily: "monospace",
              fontSize: "0.85rem",
            }}
          >
            {API_BASE}/v1
          </code>
          . All protected endpoints require{" "}
          <code
            style={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              padding: "0.1rem 0.4rem",
              fontFamily: "monospace",
              fontSize: "0.85rem",
            }}
          >
            X-API-Key: bbi_&lt;your-key&gt;
          </code>{" "}
          header.
        </p>

        {/* Quickstart */}
        <details
          style={{
            border: "1px solid var(--border)",
            borderRadius: "8px",
            marginBottom: "2rem",
            background: "var(--card)",
          }}
        >
          <summary
            style={{
              padding: "0.875rem 1.25rem",
              fontWeight: 600,
              cursor: "pointer",
              userSelect: "none",
            }}
          >
            Quickstart
          </summary>
          <div style={{ padding: "0 1.25rem 1.25rem" }}>
            <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginBottom: "1rem" }}>
              1. Get your free API key from{" "}
              <a href="/app/keys" style={{ color: "var(--accent)" }}>
                /app/keys
              </a>
              .
            </p>
            <pre
              style={{
                background: "#0f172a",
                color: "#e2e8f0",
                padding: "1rem 1.25rem",
                borderRadius: "6px",
                overflowX: "auto",
                fontSize: "0.8rem",
                lineHeight: 1.7,
              }}
            >
              <code>{`# Look up a company by CNPJ
curl https://brazil.ambern.dev/api/v1/company/12345678000195 \\
  -H "X-API-Key: bbi_your_key_here"

# Search by state and sector
curl "https://brazil.ambern.dev/api/v1/search?state=SP&size=ME&limit=20" \\
  -H "X-API-Key: bbi_your_key_here"

# Check PGFN debt + CGU sanctions (STARTER+)
curl https://brazil.ambern.dev/api/v1/company/12345678000195/compliance \\
  -H "X-API-Key: bbi_your_key_here"`}</code>
            </pre>
            <p style={{ color: "var(--muted)", fontSize: "0.875rem", marginTop: "1rem" }}>
              Every response wraps data in{" "}
              <code style={{ fontFamily: "monospace" }}>
                {`{ "data": {...}, "meta": { "plan": "STARTER", "requests_remaining": 1847 } }`}
              </code>
              . Errors use{" "}
              <code style={{ fontFamily: "monospace" }}>
                {`{ "error": { "code": "...", "message": "...", "status": 422 } }`}
              </code>
              .
            </p>
          </div>
        </details>
      </div>

      {/* Redoc mount point */}
      <div ref={containerRef} />
    </main>
  );
}
