import { test, expect } from "@playwright/test";
import { validateApiKey } from "../src/lib/api";

test("validates a key through flat metadata even when search is unavailable", async () => {
  const originalFetch = globalThis.fetch;
  const calls: string[] = [];
  globalThis.fetch = async (url, options) => {
    calls.push(String(url));
    expect(options?.headers).toEqual({ "X-API-Key": "bbi_test" });
    if (!String(url).endsWith("/v1/keys/me")) return new Response(null, { status: 500 });
    return Response.json({ plan: "FREE", requests_limit: 50, requests_this_month: 7 });
  };
  try {
    expect(await validateApiKey("bbi_test")).toEqual({ ok: true, plan: "FREE", remaining: 43 });
    expect(calls).toHaveLength(1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("invalid key returns the API error", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => Response.json(
    { error: { message: "Key not found." } }, { status: 401 },
  );
  try {
    expect(await validateApiKey("invalid")).toEqual({ ok: false, message: "Key not found." });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
