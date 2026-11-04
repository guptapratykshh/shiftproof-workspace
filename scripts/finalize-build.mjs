import { createHash } from "node:crypto";
import { readFile, writeFile, readdir } from "node:fs/promises";
const assets = (await readdir("dist/assets"))
  .sort()
  .map((name) => `/assets/${name}`);
const html = await readFile("dist/index.html", "utf8");
const fingerprint = createHash("sha256")
  .update(html + assets.join("\n"))
  .digest("hex")
  .slice(0, 16);
let worker = await readFile("public/sw.js", "utf8");
worker = worker
  .replace("shiftproof-shell-v1", `shiftproof-shell-${fingerprint}`)
  .replace(
    "cache.add('/')",
    `cache.addAll(${JSON.stringify(["/", "/favicon.svg", ...assets])})`,
  );
await writeFile("dist/sw.js", worker);
console.log(
  `Offline shell prepared: ${assets.length} static assets; no account data cached.`,
);
