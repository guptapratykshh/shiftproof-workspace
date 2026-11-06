import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
const backend = path.resolve("backend");
const python = path.join(backend, ".venv/bin/python");
if (!existsSync(python)) {
  console.error("Run: cd backend && uv sync --frozen");
  process.exit(1);
}
const migration = spawnSync(python, ["-m", "app.bootstrap"], {
  cwd: backend,
  stdio: "inherit",
});
if (migration.status !== 0) process.exit(migration.status || 1);
const children = [
  spawn(
    python,
    [
      "-m",
      "uvicorn",
      "app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      "8000",
      "--reload",
      "--no-access-log",
    ],
    { cwd: backend, stdio: "inherit" },
  ),
  spawn(python, ["-m", "app.worker"], { cwd: backend, stdio: "inherit" }),
  spawn("npm", ["run", "dev", "--", "--port", "5173", "--strictPort"], {
    stdio: "inherit",
    env: { ...process.env, VITE_API_BASE_URL: "/api/v1" },
  }),
];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill("SIGTERM");
  setTimeout(() => process.exit(code), 300).unref();
}
process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
for (const child of children) child.on("exit", (code) => stop(code || 0));
