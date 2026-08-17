#!/usr/bin/env node
/**
 * npm aliases install `@Creanova/*` folders whose package.json `name` is still
 * `@openhands/*`. Vite SSR resolves by package name and then fails with
 * "Cannot find module '@Creanova/typescript-client/...'".
 * Rewrite the name field after install so Vite and Node agree.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "..");

const PACKAGES = [
  {
    dir: "node_modules/@Creanova/typescript-client",
    name: "@Creanova/typescript-client",
  },
  {
    dir: "node_modules/@Creanova/extensions",
    name: "@Creanova/extensions",
  },
];

for (const pkg of PACKAGES) {
  const pkgJsonPath = resolve(ROOT, pkg.dir, "package.json");
  if (!existsSync(pkgJsonPath)) {
    console.warn(`[fix-creanova-aliases] skip missing ${pkg.dir}`);
    continue;
  }
  const json = JSON.parse(readFileSync(pkgJsonPath, "utf8"));
  if (json.name === pkg.name) {
    console.log(`[fix-creanova-aliases] ${pkg.name} already ok`);
    continue;
  }
  const previous = json.name;
  json.name = pkg.name;
  writeFileSync(pkgJsonPath, `${JSON.stringify(json, null, 2)}\n`);
  console.log(
    `[fix-creanova-aliases] ${pkg.dir}: name ${previous} → ${pkg.name}`,
  );
}
