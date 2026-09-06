import { test, expect } from "@playwright/test";

test("FREE key creation shows key once with no console errors", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(err.message));

  // Intercept POST /v1/keys — return a mock 201 flat payload (matching real backend shape)
  await page.route("**/v1/keys", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          key: "bbi_testkey_playwright123456789",
          plan: "FREE",
          requests_limit: 50,
          message: "Your FREE API key has been generated. Store it safely — it will not be shown again.",
        }),
      });
    } else {
      await route.continue();
    }
  });

  await page.goto("/app/keys");

  // Fill email and submit the "Get a Free Key" form
  await page.fill("#create-key-email", "playwright@example.com");
  await page.click('button:has-text("Create free key")');

  // The key should appear in the read-only input
  const keyInput = page.locator('input[readonly]');
  await expect(keyInput).toBeVisible({ timeout: 5000 });
  await expect(keyInput).toHaveValue("bbi_testkey_playwright123456789");

  // The "shown once" amber warning must be visible
  await expect(page.locator("text=Shown once")).toBeVisible();

  // Copy button must be present
  await expect(page.locator('button:has-text("Copy")')).toBeVisible();

  // No console errors / thrown exceptions
  expect(consoleErrors, `Console errors: ${consoleErrors.join("; ")}`).toHaveLength(0);
});
