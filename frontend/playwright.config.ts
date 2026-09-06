import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 20000,
  use: {
    baseURL: "http://localhost:3100",
  },
  webServer: {
    command: "npm run start",
    port: 3100,
    reuseExistingServer: true,
    timeout: 30000,
  },
});
