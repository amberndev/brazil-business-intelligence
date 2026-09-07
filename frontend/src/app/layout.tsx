import type { Metadata } from "next";
import { SiteShell } from "./Landing";
import "./globals.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://brazil.ambern.dev";
const description = "Ambern company intelligence: discover and assess Brazilian companies with public records and a REST API.";
export const metadata: Metadata = {
  title: { default: "Ambern — Company intelligence", template: "%s | Ambern" },
  description,
  metadataBase: new URL(SITE_URL),
  openGraph: { type: "website", url: SITE_URL, siteName: "Ambern", title: "Ambern — Company intelligence", description },
  twitter: { card: "summary_large_image", title: "Ambern — Company intelligence", description },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><SiteShell contactEmail={process.env.CONTACT_EMAIL ?? "vinicius@ambern.dev"}>{children}</SiteShell></body></html>;
}
