import { defineConfig } from "@playwright/test";

// Keep this long acceptance sweep independent of the existing workspace suite.
process.env.SHIFTPROOF_BROWSER_ROOT = "/tmp/shiftproof-contradiction-qa";
process.env.SHIFTPROOF_BROWSER_PORT = "8011";
process.env.SHIFTPROOF_BROWSER_FRONTEND_PORT = "5185";
process.env.SHIFTPROOF_CONTRADICTION_API = "http://127.0.0.1:8011/api/v1";

export default defineConfig({
  testDir: "./integration",
  testMatch: "contradictions.spec.ts",
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { outputFolder: "playwright-report/contradictions", open: "never" }]],
  outputDir: "test-results/contradictions",
  use: { actionTimeout: 15_000, baseURL: "http://127.0.0.1:5185", channel: "chrome", viewport: { width: 1600, height: 1000 },
    screenshot: "only-on-failure", trace: "retain-on-failure" },
  webServer: [
    { command: "PYTHONPATH=. SHIFTPROOF_BROWSER_TEST=1 .venv/bin/python tests/serve_browser_api.py",
      cwd: "./backend", url: "http://127.0.0.1:8011/api/v1/health", reuseExistingServer: false },
    { command: "VITE_API_BASE_URL=/api/v1 npx vite build --outDir .sites-runtime/contradiction-dist && SHIFTPROOF_API_TARGET=http://127.0.0.1:8011 npx vite preview --outDir .sites-runtime/contradiction-dist --host 127.0.0.1 --port 5185 --strictPort",
      url: "http://127.0.0.1:5185", reuseExistingServer: false },
  ],
});
