import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://brazil.ambern.dev";

export const metadata: Metadata = {
  title: {
    default: "Brazil Business Intelligence — Verify Any Brazilian Company",
    template: "%s | Brazil Business Intelligence",
  },
  description:
    "Instant access to 72M+ Brazilian companies: CNPJ lookup, compliance checks, shareholder data, and market intelligence via REST API.",
  metadataBase: new URL(SITE_URL),
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "Brazil Business Intelligence",
    title: "Brazil Business Intelligence",
    description:
      "Verify Any Brazilian Company in Milliseconds. 72M+ companies, PGFN debt, CGU sanctions, shareholders.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Brazil Business Intelligence",
    description:
      "Verify Any Brazilian Company in Milliseconds. 72M+ companies, PGFN debt, CGU sanctions, shareholders.",
  },
};

// TODO(frontend): footer links — empty configurable array
const FOOTER_LINKS: { label: string; href: string }[] = [];

// TODO(frontend): replace with real logo
function AmberLogo() {
  return (
    <svg
      width="120"
      height="32"
      viewBox="0 0 120 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Ambern"
    >
      <text
        x="0"
        y="24"
        fontFamily="system-ui, sans-serif"
        fontSize="22"
        fontWeight="700"
        fill="currentColor"
        letterSpacing="-0.5"
      >
        Ambern
      </text>
    </svg>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <nav
          id="site-nav"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "1rem 2rem",
            borderBottom: "1px solid var(--border)",
            position: "sticky",
            top: 0,
            background: "var(--background)",
            zIndex: 50,
          }}
        >
          <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
            <AmberLogo />
          </Link>
          <div style={{ display: "flex", gap: "1.5rem", alignItems: "center" }}>
            <Link
              href="/docs"
              style={{ color: "var(--muted)", textDecoration: "none", fontSize: "0.875rem" }}
            >
              Docs
            </Link>
            <Link
              href="/app/search"
              style={{ color: "var(--muted)", textDecoration: "none", fontSize: "0.875rem" }}
            >
              Search
            </Link>
            <Link
              href="/app/keys"
              style={{
                background: "var(--accent)",
                color: "#fff",
                padding: "0.4rem 1rem",
                borderRadius: "6px",
                textDecoration: "none",
                fontSize: "0.875rem",
                fontWeight: 600,
              }}
            >
              API Key
            </Link>
          </div>
        </nav>

        <main style={{ minHeight: "calc(100vh - 130px)" }}>{children}</main>

        <footer
          id="site-footer"
          style={{
            borderTop: "1px solid var(--border)",
            padding: "2rem",
            display: "flex",
            flexDirection: "column",
            gap: "1rem",
            alignItems: "center",
            textAlign: "center",
          }}
        >
          <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
            <AmberLogo />
          </Link>
          {FOOTER_LINKS.length > 0 && (
            <nav style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", justifyContent: "center" }}>
              {FOOTER_LINKS.map((link) => (
                <Link
                  key={link.label}
                  href={link.href}
                  style={{ color: "var(--muted)", textDecoration: "none", fontSize: "0.875rem" }}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          )}
          <div style={{ display: "flex", gap: "1.25rem", flexWrap: "wrap", justifyContent: "center" }}>
            <a
              href="mailto:vinicius@ambern.dev"
              style={{ color: "var(--muted)", textDecoration: "none", fontSize: "0.8rem" }}
            >
              Contact
            </a>
            <a
              href="https://ambern.dev"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "var(--muted)", textDecoration: "none", fontSize: "0.8rem" }}
            >
              ambern.dev
            </a>
          </div>
          <p style={{ color: "var(--muted)", fontSize: "0.8rem", margin: 0 }}>
            © {new Date().getFullYear()} Ambern. All rights reserved.
          </p>
        </footer>
      </body>
    </html>
  );
}
