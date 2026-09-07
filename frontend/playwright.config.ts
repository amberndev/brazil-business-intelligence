import { defineConfig } from "@playwright/test";

const port = Number(process.env.PLAYWRIGHT_PORT ?? 3100);

export default defineConfig({
  testDir: "./tests",
  timeout: 20000,
  use: {
    baseURL: `http://localhost:${port}`,
  },
  webServer: {
    command: `npx next start -p ${port}`,
    port,
    reuseExistingServer: !process.env.PLAYWRIGHT_PORT,
    timeout: 30000,
  },
});
