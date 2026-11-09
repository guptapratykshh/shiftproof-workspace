import { defineConfig } from "@playwright/test";

process.env.SHIFTPROOF_BROWSER_ROOT = "/tmp/shiftproof-dialogue-qa";
process.env.SHIFTPROOF_BROWSER_PORT = "8013";
process.env.SHIFTPROOF_BROWSER_FRONTEND_PORT = "5187";
process.env.SHIFTPROOF_DIALOGUE_FIXTURES = "1";

// Atlas fixtures exercise the real transaction path and need network time for
// setup and the transcription -> extraction -> speech job chain.
const usesMongo = Boolean(process.env.SHIFTPROOF_BROWSER_DATABASE_URL);

export default defineConfig({
  testDir: "./integration",
  testMatch: "dialogue.spec.ts",
  workers: 1,
  timeout: usesMongo ? 360000 : 90000,
  expect: { timeout: usesMongo ? 90000 : 20000 },
  reporter: "list",
  outputDir: "test-results/dialogue",
  use: {
    baseURL: "http://127.0.0.1:5187",
    channel: "chrome",
    viewport: { width: 1470, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        "PYTHONPATH=. SHIFTPROOF_BROWSER_TEST=1 .venv/bin/python tests/serve_browser_api.py",
      cwd: "./backend",
      url: "http://127.0.0.1:8013/api/v1/health",
      reuseExistingServer: false,
      timeout: usesMongo ? 180000 : 60000,
    },
    {
      command:
        "VITE_API_BASE_URL=/api/v1 npx vite build --outDir .sites-runtime/dialogue-dist && SHIFTPROOF_API_TARGET=http://127.0.0.1:8013 npx vite preview --outDir .sites-runtime/dialogue-dist --host 127.0.0.1 --port 5187 --strictPort",
      url: "http://127.0.0.1:5187",
      reuseExistingServer: false,
    },
  ],
});
