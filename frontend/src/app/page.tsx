import type { Metadata } from "next";
import Landing from "./Landing";

export const metadata: Metadata = {
  title: "Discover and assess Brazilian companies",
  description: "Ambern company intelligence: discover Brazilian companies, assess public records and integrate company data through an API.",
};

export default function LandingPage() {
  return <Landing contactEmail={process.env.CONTACT_EMAIL ?? "vinicius@ambern.dev"} />;
}
