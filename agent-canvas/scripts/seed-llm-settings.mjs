/**
 * Seed Creanova LLM settings into a running local agent-server.
 *
 * Used on new machines so onboarding / first conversation match the
 * standard LiteLLM endpoint without hand-editing Settings.
 *
 * Env (optional overrides; defaults come from config/defaults.json → llm):
 *   CREANOVA_LLM_MODEL
 *   CREANOVA_LLM_BASE_URL
 *   CREANOVA_LLM_API_KEY   (User Virtual Key, sk-… — never commit)
 *   CREANOVA_LLM_PROFILE   (default: nemotron-3-nano)
 *   CREANOVA_LLM_SEED=0    to skip
 *   OH_CANVAS_SAFE_BACKEND_PORT / OH_CANVAS_SAFE_STATE_DIR
 */
import { readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { homedir } from "node:os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, "..");

function loadDefaults() {
  const path = join(projectRoot, "config", "defaults.json");
  const raw = JSON.parse(readFileSync(path, "utf8"));
  return raw.llm ?? {};
}

function resolveStateDir() {
  return (
    process.env.OH_CANVAS_SAFE_STATE_DIR ||
    join(homedir(), ".creanova", "agent-canvas")
  );
}

function readSessionApiKey() {
  const stateDir = resolveStateDir();
  const candidates = [
    process.env.OH_SESSION_API_KEY_PATH,
    join(stateDir, "api-key.txt"),
    join(homedir(), ".creanova", "agent-canvas", "api-key.txt"),
  ].filter(Boolean);
  for (const file of candidates) {
    if (existsSync(file)) {
      return readFileSync(file, "utf8").trim();
    }
  }
  return null;
}

function resolveLlmConfig() {
  const defaults = loadDefaults();
  return {
    model:
      process.env.CREANOVA_LLM_MODEL ||
      process.env.VITE_CREANOVA_LLM_MODEL ||
      defaults.model,
    baseUrl:
      process.env.CREANOVA_LLM_BASE_URL ||
      process.env.VITE_CREANOVA_LLM_BASE_URL ||
      defaults.baseUrl,
    apiKey: process.env.CREANOVA_LLM_API_KEY?.trim() || null,
    profileName:
      process.env.CREANOVA_LLM_PROFILE ||
      defaults.profileName ||
      "nemotron-3-nano",
  };
}

async function request(base, sessionKey, method, path, body) {
  const res = await fetch(`${base}${path}`, {
    method,
    headers: {
      "X-Session-API-Key": sessionKey,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = { raw: text };
  }
  return { ok: res.ok, status: res.status, json };
}

/**
 * @param {{ agentServerPort?: number, log?: (msg: string) => void }} [options]
 * @returns {Promise<boolean>}
 */
export async function seedLlmSettings(options = {}) {
  if (process.env.CREANOVA_LLM_SEED === "0") {
    options.log?.("LLM seed skipped (CREANOVA_LLM_SEED=0)");
    return false;
  }

  const port =
    options.agentServerPort ??
    Number(process.env.OH_CANVAS_SAFE_BACKEND_PORT || 18000);
  const base = `http://127.0.0.1:${port}`;
  const sessionKey = readSessionApiKey();
  if (!sessionKey) {
    options.log?.("LLM seed skipped: session API key not found yet");
    return false;
  }

  const cfg = resolveLlmConfig();
  if (!cfg.model || !cfg.baseUrl) {
    options.log?.("LLM seed skipped: model/baseUrl missing from defaults");
    return false;
  }

  const llm = {
    model: cfg.model,
    base_url: cfg.baseUrl,
    auth_type: "api_key",
    ...(cfg.apiKey ? { api_key: cfg.apiKey } : {}),
  };

  const patch = await request(base, sessionKey, "PATCH", "/api/settings", {
    agent_settings_diff: { llm },
  });
  if (!patch.ok) {
    options.log?.(
      `LLM settings PATCH failed (${patch.status}): ${JSON.stringify(patch.json)}`,
    );
    return false;
  }

  const saveProfile = await request(
    base,
    sessionKey,
    "POST",
    `/api/profiles/${encodeURIComponent(cfg.profileName)}`,
    { llm, include_secrets: Boolean(cfg.apiKey) },
  );
  if (!saveProfile.ok && saveProfile.status !== 201) {
    options.log?.(
      `LLM profile save failed (${saveProfile.status}): ${JSON.stringify(saveProfile.json)}`,
    );
  } else {
    await request(
      base,
      sessionKey,
      "POST",
      `/api/profiles/${encodeURIComponent(cfg.profileName)}/activate`,
    );
    await request(base, sessionKey, "POST", "/api/agent-profiles/default", {
      agent_kind: "openhands",
      llm_profile_ref: cfg.profileName,
    });
  }

  options.log?.(
    `LLM seeded: ${cfg.model} @ ${cfg.baseUrl}` +
      (cfg.apiKey ? " (api key set)" : " (api key missing — set CREANOVA_LLM_API_KEY)"),
  );
  return true;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  seedLlmSettings({
    log: (msg) => console.log(msg),
  }).then((ok) => {
    process.exit(ok ? 0 : 1);
  });
}
