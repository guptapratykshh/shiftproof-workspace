import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./integration",
  // Voice fixtures run their own API on 8013 via playwright.dialogue.config.ts.
  testIgnore: "dialogue.spec.ts",
  workers: 1,
  fullyParallel: false,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: "list",
  outputDir: "test-results/workspace",
  use: {
    baseURL: "http://127.0.0.1:5175",
    channel: "chrome",
    viewport: { width: 1600, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        "PYTHONPATH=. SHIFTPROOF_BROWSER_TEST=1 .venv/bin/python tests/serve_browser_api.py",
      cwd: "./backend",
      url: "http://127.0.0.1:8001/api/v1/health",
      reuseExistingServer: false,
    },
    {
      command:
        process.env.SHIFTPROOF_BUILD_TEST === "1"
          ? "VITE_API_BASE_URL=/api/v1 npm run build && SHIFTPROOF_API_TARGET=http://127.0.0.1:8001 npm run preview -- --port 5175 --strictPort"
          : "VITE_API_BASE_URL=/api/v1 SHIFTPROOF_API_TARGET=http://127.0.0.1:8001 npm run dev -- --port 5175 --strictPort",
      url: "http://127.0.0.1:5175",
      reuseExistingServer: false,
    },
  ],
});
