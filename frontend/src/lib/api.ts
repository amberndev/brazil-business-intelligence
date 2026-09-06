import type {
  ApiResponse,
  ApiError,
  HealthResponse,
  CompanyProfile,
  CompanyCompliance,
  CompanyShareholders,
  BatchRequest,
  BatchResponse,
  SearchResponse,
  MarketOverview,
} from "./api-types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100";

const API_KEY_STORAGE = "bbi_api_key";

export function getStoredApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(API_KEY_STORAGE);
}

export function setStoredApiKey(key: string): void {
  localStorage.setItem(API_KEY_STORAGE, key);
}

export function clearStoredApiKey(): void {
  localStorage.removeItem(API_KEY_STORAGE);
}

type FetchResult<T> =
  | { ok: true; data: T; meta: ApiResponse<T>["meta"] }
  | { ok: false; error: ApiError["error"] };

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  apiKey?: string | null
): Promise<FetchResult<T>> {
  const key = apiKey ?? getStoredApiKey();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(key ? { "X-API-Key": key } : {}),
    ...(options.headers as Record<string, string> | undefined),
  };

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    return {
      ok: false,
      error: { code: "network_error", message: "Cannot reach the API server.", status: 0 },
    };
  }

  if (res.ok) {
    const json = (await res.json()) as ApiResponse<T>;
    return { ok: true, data: json.data, meta: json.meta };
  }

  let errBody: ApiError;
  try {
    errBody = (await res.json()) as ApiError;
  } catch {
    errBody = { error: { code: "unknown_error", message: res.statusText, status: res.status } };
  }
  return { ok: false, error: errBody.error };
}

// ---- Health (public, no auth) ----

export async function fetchHealth(): Promise<HealthResponse | null> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/v1/health`);
    if (!res.ok) return null;
    return (await res.json()) as HealthResponse;
  } catch {
    return null;
  }
}

/** Validates a key by calling the health-adjacent path; returns meta on success. */
export async function validateApiKey(
  key: string
): Promise<{ ok: true; plan: string; remaining: number } | { ok: false; message: string }> {
  // We validate by attempting a lightweight authenticated call (company search with limit=1)
  const result = await apiFetch<SearchResponse>(
    "/v1/search?limit=1",
    {},
    key
  );
  if (result.ok) {
    return { ok: true, plan: result.meta.plan, remaining: result.meta.requests_remaining };
  }
  return { ok: false, message: result.error.message };
}

// ---- POST /v1/keys — self-serve FREE key creation ----

export type CreateKeyResponse =
  | { ok: true; key: string; plan: string; email: string }
  | { ok: false; code: string; message: string };

export async function createFreeApiKey(email: string): Promise<CreateKeyResponse> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/v1/keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
  } catch {
    return { ok: false, code: "network_error", message: "Cannot reach the API server." };
  }

  if (res.status === 201) {
    // Backend returns a flat object (NOT the standard {data:…} envelope)
    const json = (await res.json()) as { key: string; plan: string; requests_limit: number; message: string };
    return { ok: true, key: json.key, plan: json.plan, email };
  }

  let errBody: ApiError;
  try {
    errBody = (await res.json()) as ApiError;
  } catch {
    errBody = { error: { code: "unknown_error", message: res.statusText, status: res.status } };
  }
  return { ok: false, code: errBody.error.code, message: errBody.error.message };
}

// ---- Remaining endpoints (real implementations — all 7 endpoints wired) ----

export async function fetchCompanyProfile(
  cnpj: string
): Promise<FetchResult<CompanyProfile>> {
  return apiFetch<CompanyProfile>(`/v1/company/${cnpj}`);
}

export async function fetchCompanyCompliance(
  cnpj: string
): Promise<FetchResult<CompanyCompliance>> {
  return apiFetch<CompanyCompliance>(`/v1/company/${cnpj}/compliance`);
}

export async function fetchCompanyShareholders(
  cnpj: string
): Promise<FetchResult<CompanyShareholders>> {
  return apiFetch<CompanyShareholders>(`/v1/company/${cnpj}/shareholders`);
}

export async function fetchSearch(
  params: Record<string, string | number | boolean>
): Promise<FetchResult<SearchResponse>> {
  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  ).toString();
  return apiFetch<SearchResponse>(`/v1/search?${qs}`);
}

export async function fetchBatch(
  body: BatchRequest
): Promise<FetchResult<BatchResponse>> {
  return apiFetch<BatchResponse>("/v1/company/batch", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchMarketOverview(
  params?: { state?: string; sector?: string }
): Promise<FetchResult<MarketOverview>> {
  const qs = params
    ? new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][]
      ).toString()
    : "";
  return apiFetch<MarketOverview>(`/v1/market/overview${qs ? "?" + qs : ""}`);
}
