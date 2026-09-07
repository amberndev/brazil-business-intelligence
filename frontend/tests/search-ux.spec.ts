import { test, expect } from "@playwright/test";

const result = (name = "Banco do Brasil") => ({ data: { results: [{ cnpj: "00000000017086", cnpj_formatted: "00.000.000/0170-86", name, city: "Brasilia", state: "DF", sector: null, status: "ATIVA", has_debt: false }], pagination: { page: 1, limit: 20, total: 1, total_pages: 1 } }, meta: {} });
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("bbi_api_key", "test-key"));
});

test("search submits explicitly, normalizes CNPJ, and applies contact/city filters on mobile", async ({ page }) => {
  const calls: URL[] = [];
  await page.route("**/v1/search?**", async route => { calls.push(new URL(route.request().url())); await route.fulfill({ json: result() }); });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/app/search");
  await page.getByLabel("Company name or CNPJ").fill("00.000.000/0170-86");
  await page.getByLabel("City", { exact: true }).fill("Brasilia");
  await page.getByLabel("Has email", { exact: true }).check();
  await page.getByLabel("Has phone", { exact: true }).check();
  expect(calls).toHaveLength(0);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("link", { name: "Banco do Brasil" })).toBeVisible();
  expect(calls).toHaveLength(1);
  expect(Object.fromEntries(calls[0].searchParams)).toMatchObject({ q: "00000000017086", city: "Brasilia", has_email: "true", has_phone: "true" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByLabel("Company name or CNPJ").fill("Banco do Brasil");
  expect(calls).toHaveLength(1);
  await page.getByLabel("Company name or CNPJ").press("Enter");
  await expect.poll(() => calls.length).toBe(2);
  expect(calls[1].searchParams.get("q")).toBe("Banco do Brasil");
});

test("newer search wins when the previous response arrives late", async ({ page }) => {
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  let oldStarted = false;
  await page.route("**/v1/search?**", async route => {
    const old = new URL(route.request().url()).searchParams.get("q") === "old";
    if (old) { oldStarted = true; await held; }
    await route.fulfill({ json: result(old ? "Old result" : "New result") }).catch(() => {});
  });
  await page.goto("/app/search");
  await page.getByLabel("Company name or CNPJ").fill("old");
  await page.getByLabel("Company name or CNPJ").press("Enter");
  await expect.poll(() => oldStarted).toBe(true);
  await page.getByLabel("Company name or CNPJ").fill("new");
  await page.getByLabel("Company name or CNPJ").press("Enter");
  await expect(page.getByRole("link", { name: "New result" })).toBeVisible();
  release();
  await expect(page.getByRole("link", { name: "Old result" })).toHaveCount(0);
});

test("missing company shows one error and does not request restricted sections", async ({ page }) => {
  const calls: string[] = [];
  await page.route("**/v1/company/**", async route => {
    calls.push(route.request().url());
    await route.fulfill({ status: 404, json: { error: { code: "not_found", message: "Company not found", status: 404 } } });
  });
  await page.goto("/app/company/00000000017086");
  await expect(page.locator("#company-header").getByRole("alert")).toHaveText("Company not found. Check the CNPJ or return to search.");
  await expect(page.locator("#company-overview, #company-compliance, #company-shareholders")).toHaveCount(0);
  expect(calls).toHaveLength(1);
});

test("profile success retains plan restrictions for additional sections", async ({ page }) => {
  await page.route("**/v1/company/**", async route => {
    if (/\/(compliance|shareholders)$/.test(route.request().url())) {
      await route.fulfill({ status: 403, json: { error: { code: "plan_forbidden", message: "Restricted", status: 403 } } });
      return;
    }
    await route.fulfill({ json: { data: { cnpj: "00000000017086", cnpj_formatted: "00.000.000/0170-86", razao_social: "Banco", status: "ATIVA", location: {}, sector: { secondary_cnae: [] }, contact: {} }, meta: {} } });
  });
  await page.goto("/app/company/00000000017086");
  await expect(page.getByText("Compliance data requires STARTER plan or above.")).toBeVisible();
  await expect(page.getByText("Shareholder data requires STARTER plan or above.")).toBeVisible();
});
