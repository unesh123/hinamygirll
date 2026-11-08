#!/usr/bin/env node
// Point every Vercel rewrite at one API origin.
//
//   node scripts/set-api-origin.mjs https://hinaa-api.onrender.com
//   node scripts/set-api-origin.mjs --show
//
// Rewrites absolute-URL destinations in vercel.json, apps/web/vercel.json and
// (if present) .vercel/output/config.json; relative destinations such as the
// SPA fallback "/index.html" are left alone. Idempotent.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const targets = [
  join(root, "vercel.json"),
  join(root, "apps", "web", "vercel.json"),
  join(root, ".vercel", "output", "config.json"),
].filter(existsSync);

const arg = process.argv[2];
const absolute = /^https?:\/\/[^/]+/i;

function rewriteLists(config) {
  // vercel.json uses `rewrites`; Build Output API config.json uses `routes` with `dest`.
  const lists = [];
  if (Array.isArray(config.rewrites)) lists.push([config.rewrites, "destination"]);
  if (Array.isArray(config.routes)) lists.push([config.routes, "dest"]);
  return lists;
}

if (arg === "--show") {
  for (const file of targets) {
    const origins = new Set();
    for (const [list, key] of rewriteLists(JSON.parse(readFileSync(file, "utf8")))) {
      for (const item of list) {
        const match = typeof item[key] === "string" && item[key].match(absolute);
        if (match) origins.add(match[0]);
      }
    }
    console.log(`${file}: ${[...origins].join(", ") || "(none)"}`);
  }
  process.exit(0);
}

let origin;
try {
  const parsed = new URL(arg ?? "");
  const local = ["localhost", "127.0.0.1"].includes(parsed.hostname);
  if (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && local)) throw new Error("scheme");
  if (parsed.username || parsed.password || parsed.search || parsed.hash || !["", "/"].includes(parsed.pathname)) {
    throw new Error("shape");
  }
  origin = parsed.origin;
} catch {
  console.error("usage: node scripts/set-api-origin.mjs <https://api-origin> | --show");
  console.error("The origin must be a bare https URL (http only for localhost), no path or credentials.");
  process.exit(2);
}

let changed = 0;
for (const file of targets) {
  const original = readFileSync(file, "utf8");
  const config = JSON.parse(original);
  for (const [list, key] of rewriteLists(config)) {
    for (const item of list) {
      if (typeof item[key] === "string" && absolute.test(item[key])) {
        item[key] = item[key].replace(absolute, origin);
      }
    }
  }
  const updated = JSON.stringify(config, null, 2) + (original.endsWith("\n") ? "\n" : "");
  if (updated !== original) {
    writeFileSync(file, updated);
    changed += 1;
    console.log(`updated ${file}`);
  } else {
    console.log(`unchanged ${file}`);
  }
}
console.log(`API origin is now ${origin} (${changed} file(s) changed)`);
