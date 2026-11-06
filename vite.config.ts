import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    watch: {
      // Generating QA reports or runtime artifacts must not reload a worker's
      // in-progress form in the live development preview.
      ignored: ["**/.sites-*/**", "**/test-results/**", "**/playwright-report/**", "**/artifacts/**", "**/backend/**"],
    },
    fs: {
      // A forwarded development server must never serve backend or runtime files.
      deny: [
        "**/.env",
        "**/.env.*",
        "**/*.{crt,pem}",
        "**/.git/**",
        "**/backend/**",
        "**/.sites-*/**",
        "**/data/**",
        "**/backups/**",
        "**/test-results/**",
        "**/playwright-report/**",
        "**/*.{db,db-shm,db-wal,sqlite,sqlite3,dump,eml,log}",
      ],
    },
    proxy: {
      "/api": process.env.SHIFTPROOF_API_TARGET || "http://127.0.0.1:8000",
    },
  },
});
