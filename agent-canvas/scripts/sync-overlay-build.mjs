#!/usr/bin/env node
/**
 * Publish a finished staging overlay into ./build without emptying it first.
 *
 * Why: agent-canvas bind-mounts ./build. A normal `react-router build` runs
 * emptyOutDir against that path, so :18000/agents goes blank mid-build. Building
 * into build.staging then syncing here keeps the live mount intact.
 *
 * Order: copy everything except index.html first, then index.html last, then
 * prune stale files — so browsers never see a new index pointing at deleted hashes.
 */
import { cp, lstat, mkdir, readdir, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const stagingDir = path.resolve(
  root,
  process.env.OVERLAY_BUILD_DIR?.trim() || "build.staging",
);
const liveDir = path.resolve(root, "build");

async function pathExists(p) {
  try {
    await lstat(p);
    return true;
  } catch (error) {
    if (error && error.code === "ENOENT") return false;
    throw error;
  }
}

async function listRelFiles(dir, prefix = "") {
  const entries = await readdir(dir, { withFileTypes: true });
  const out = [];
  for (const entry of entries) {
    const rel = prefix ? path.join(prefix, entry.name) : entry.name;
    const abs = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...(await listRelFiles(abs, rel)));
    } else if (entry.isFile() || entry.isSymbolicLink()) {
      out.push(rel);
    }
  }
  return out;
}

async function copyFile(rel) {
  const src = path.join(stagingDir, rel);
  const dest = path.join(liveDir, rel);
  await mkdir(path.dirname(dest), { recursive: true });
  await cp(src, dest, { force: true });
}

async function main() {
  if (!(await pathExists(path.join(stagingDir, "index.html")))) {
    console.error(
      `[sync-overlay-build] missing ${path.join(stagingDir, "index.html")} — build staging first`,
    );
    process.exit(1);
  }

  await mkdir(liveDir, { recursive: true });
  const stagingFiles = await listRelFiles(stagingDir);
  const deferred = stagingFiles.filter(
    (rel) => path.basename(rel) === "index.html",
  );
  const firstPass = stagingFiles.filter(
    (rel) => path.basename(rel) !== "index.html",
  );

  for (const rel of firstPass) {
    await copyFile(rel);
  }
  for (const rel of deferred) {
    await copyFile(rel);
  }

  const liveFiles = await listRelFiles(liveDir);
  const keep = new Set(stagingFiles);
  for (const rel of liveFiles) {
    if (!keep.has(rel)) {
      await rm(path.join(liveDir, rel), { force: true });
    }
  }

  console.log(
    `[sync-overlay-build] published ${stagingFiles.length} files → ${liveDir}`,
  );
}

main().catch((error) => {
  console.error("[sync-overlay-build] failed:", error);
  process.exit(1);
});
