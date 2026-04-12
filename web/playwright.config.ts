import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  webServer: {
    command: "SCANNER_API_MODE=mock npm run dev",
    port: 3000,
    reuseExistingServer: true,
    timeout: 120000,
  },
});
