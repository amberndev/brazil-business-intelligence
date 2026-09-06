// ---- envelope ----
export interface ApiMeta {
  query_time_ms: number;
  plan: PlanTier;
  requests_remaining: number; // -1 = unlimited
}
export interface ApiResponse<T> {
  data: T;
  meta: ApiMeta;
}
export interface ApiError {
  error: { code: string; message: string; status: number };
}
export type PlanTier = "FREE" | "STARTER" | "PRO" | "ENTERPRISE";
export type CompanySize = "MEI" | "ME" | "EPP" | "MEDIO" | "GRANDE";
export type CompanyStatus = "ATIVA" | "BAIXADA" | "SUSPENSA";

// ---- 1. health (unwrapped) ----
export interface HealthResponse {
  status: "ok" | "degraded";
  db: "ok" | "error";
  redis: "ok" | "memory-fallback";
  version: string;
}

// ---- 2. company profile ----
export interface CompanyProfile {
  cnpj: string;                 // 14 digits, unmasked
  cnpj_formatted: string;       // "12.345.678/0001-95"
  razao_social: string;
  nome_fantasia: string | null;
  status: CompanyStatus;
  size: CompanySize | null;
  opened_at: string | null;     // ISO date "YYYY-MM-DD"
  legal_nature: string | null;  // natureza jurídica
  share_capital: number | null; // capital social (BRL)
  location: {
    street: string | null;
    number: string | null;
    complement: string | null;
    district: string | null;    // bairro
    city: string | null;
    state: string | null;       // UF
    zip: string | null;         // CEP
  };
  sector: {
    primary_cnae: { code: string; description: string | null } | null;
    secondary_cnae: { code: string; description: string | null }[];
  };
  contact: {
    phone: string | null;
    email: string | null;
  };
}

// ---- 3. compliance ----
export interface CompanyCompliance {
  cnpj: string;
  pgfn_debt: {
    has_debt: boolean;
    total_amount: number;       // BRL
    records_count: number;
  };
  cgu_sanctions: {
    has_sanctions: boolean;
    count: number;
    items: {
      type: string;             // e.g. sanction category
      description: string | null;
      start_date: string | null;
      end_date: string | null;
    }[];
  };
}

// ---- 4. shareholders ----
export interface Shareholder {
  name: string;
  document: string | null;      // masked/partial only — never full CPF
  role: string | null;          // qualificação do sócio
  participation_pct: number | null;
  since: string | null;         // ISO date
}
export interface CompanyShareholders {
  cnpj: string;
  count: number;
  shareholders: Shareholder[];
}

// ---- 5. batch ----
export interface BatchRequest { cnpjs: string[]; }         // 1..50
export interface BatchItemResult {
  cnpj: string;                                            // normalized input
  profile: CompanyProfile | null;
  error: { code: string; message: string } | null;        // set when profile null
}
export interface BatchResponse {
  count: number;
  results: BatchItemResult[];
}

// ---- 6. search ----
export interface SearchResultRow {
  cnpj: string;
  cnpj_formatted: string;
  name: string;                 // nome fantasia || razão social
  city: string | null;
  state: string | null;         // UF
  sector: string | null;        // primary CNAE description
  status: CompanyStatus;
  has_debt: boolean;            // drives the debt badge
}
export interface Pagination {
  page: number;
  limit: number;
  total: number;                // total matching rows
  total_pages: number;
}
export interface SearchResponse {
  results: SearchResultRow[];
  pagination: Pagination;
}

// ---- 7. market overview ----
export interface MarketOverview {
  total_companies: number;
  by_state: { state: string; count: number }[];
  by_sector: { cnae: string; description: string | null; count: number }[];
}
