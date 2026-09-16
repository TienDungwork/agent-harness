/**
 * LiteLLM requires a provider-qualified model id (e.g. ``openai/gpt-4o``).
 * Bare names like ``nemotron-3-nano:4b`` or ``auto`` fail with
 * ``LLM Provider NOT provided`` even when ``base_url`` points at an
 * OpenAI-compatible proxy.
 */

const PROVIDER_SEPARATOR = "/";

/** Hosts that are not OpenAI-compatible chat-completions endpoints for LiteLLM. */
const UNSUPPORTED_LLM_HOST_MARKERS = ["api.cursor.com"] as const;

/** Bare model ids that are product aliases, not LiteLLM models. */
const UNSUPPORTED_BARE_MODELS = new Set(["auto", "cursorauto"]);

export function hasLlmProviderPrefix(model: string): boolean {
  const slash = model.indexOf(PROVIDER_SEPARATOR);
  return slash > 0 && slash < model.length - 1;
}

export function llmModelsMatch(
  a: string | null | undefined,
  b: string | null | undefined,
): boolean {
  if (!a || !b) return false;
  if (a === b) return true;
  const bareA = hasLlmProviderPrefix(a) ? a.slice(a.indexOf("/") + 1) : a;
  const bareB = hasLlmProviderPrefix(b) ? b.slice(b.indexOf("/") + 1) : b;
  return bareA === bareB || a === `openai/${bareB}` || b === `openai/${bareA}`;
}

/**
 * When a custom OpenAI-compatible ``base_url`` is set and the model has no
 * provider prefix, LiteLLM still needs ``openai/...`` so it knows which
 * provider adapter to use. The remote host then receives the bare model name.
 */
export function normalizeLlmModelForLiteLLM(
  model: string,
  baseUrl?: string | null,
): string {
  const trimmed = model.trim();
  if (!trimmed || hasLlmProviderPrefix(trimmed)) return trimmed;
  if (baseUrl && baseUrl.trim()) {
    return `openai/${trimmed}`;
  }
  return trimmed;
}

/**
 * OpenAI-compatible proxies (Ollama/LiteLLM tunnels) expect ``.../v1``.
 * Users often paste the tunnel host root; LiteLLM then calls ``/chat/completions``
 * and gets FastAPI ``{"detail":"Not Found"}``.
 */
export function normalizeOpenAiCompatibleBaseUrl(
  baseUrl?: string | null,
): string | null | undefined {
  if (baseUrl == null) return baseUrl;
  const trimmed = baseUrl.trim();
  if (!trimmed) return trimmed;
  try {
    const url = new URL(trimmed);
    const path = url.pathname.replace(/\/+$/, "") || "";
    if (path === "" || path === "/") {
      url.pathname = "/v1";
      return url.toString().replace(/\/$/, "");
    }
    return trimmed.replace(/\/+$/, "");
  } catch {
    return trimmed.replace(/\/+$/, "");
  }
}

/**
 * Hosted OpenAI-family APIs accept LiteLLM's ``stream_options.include_usage``.
 * Strict OpenAI-compatible gateways (LAN IPs, *.local, Cloudflare tunnels)
 * reject it with 400 ``param=stream_options``.
 */
/** RFC1918 / loopback / *.local LLM hosts (LAN vLLM, local gateways). */
export function isPrivateOrLocalLlmEndpoint(
  baseUrl?: string | null,
): boolean {
  if (!baseUrl?.trim()) return false;
  let host: string;
  try {
    host = new URL(baseUrl).hostname.toLowerCase();
  } catch {
    return true;
  }
  if (
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "::1" ||
    host.endsWith(".local") ||
    host === "host.docker.internal"
  ) {
    return true;
  }
  if (/^10\./.test(host) || /^192\.168\./.test(host)) return true;
  const m = /^172\.(\d+)\./.exec(host);
  if (m) {
    const second = Number(m[1]);
    if (second >= 16 && second <= 31) return true;
  }
  return false;
}

export function llmEndpointSupportsOpenAiStreamOptions(
  baseUrl?: string | null,
): boolean {
  if (!baseUrl?.trim()) return true;
  let host: string;
  try {
    host = new URL(baseUrl).hostname.toLowerCase();
  } catch {
    return false;
  }
  if (
    host === "api.openai.com" ||
    host.endsWith(".openai.com") ||
    host.endsWith(".openai.azure.com") ||
    host === "api.anthropic.com" ||
    host.endsWith(".anthropic.com") ||
    host.endsWith(".googleapis.com") ||
    host === "openrouter.ai" ||
    host.endsWith(".openrouter.ai")
  ) {
    return true;
  }
  return false;
}

const STRICT_ENDPOINT_DROP_KEYS = [
  "reasoning_effort",
  "extended_thinking_budget",
  "enable_encrypted_reasoning",
  "prompt_cache_retention",
] as const;

/** Disable streaming extras that LAN OpenAI-compatible gateways reject. */
export function applyStrictOpenAiCompatibleLlmGuards(
  llm: Record<string, unknown>,
): void {
  const baseUrl = typeof llm.base_url === "string" ? llm.base_url : null;
  if (llmEndpointSupportsOpenAiStreamOptions(baseUrl)) return;
  llm.stream = false;
  for (const key of STRICT_ENDPOINT_DROP_KEYS) {
    delete llm[key];
  }
  // Private LAN Ollama / vLLM gateways: string content + no native tools.
  if (isPrivateOrLocalLlmEndpoint(baseUrl)) {
    llm.force_string_serializer = true;
    llm.native_tool_calling = false;
    llm.caching_prompt = false;
  }
}

/** Strip LiteLLM provider prefix (`openai/qwen3:4b` → `qwen3:4b`). */
export function bareLlmModelId(model: string): string {
  const trimmed = model.trim();
  if (!hasLlmProviderPrefix(trimmed)) return trimmed;
  return trimmed.slice(trimmed.indexOf(PROVIDER_SEPARATOR) + 1);
}

function normalizeGatewayModelId(id: string): string {
  return id.trim().replace(/:latest$/i, "");
}

/**
 * Candidate aliases when the user typed a near-miss id
 * (``qwen3-4b`` ↔ ``qwen3:4b``, optional ``:latest``).
 */
export function llmModelIdAliases(model: string): string[] {
  const bare = bareLlmModelId(model);
  const noLatest = normalizeGatewayModelId(bare);
  const swapped =
    noLatest.includes(":")
      ? noLatest.replace(/:/g, "-")
      : noLatest.replace(/-/g, ":");
  const out = new Set<string>([
    bare,
    noLatest,
    `${noLatest}:latest`,
    swapped,
    `${swapped}:latest`,
  ]);
  return [...out].filter(Boolean);
}

export function findGatewayModelMatch(
  requestedModel: string,
  availableIds: string[],
): string | null {
  const availableNorm = new Map<string, string>();
  for (const id of availableIds) {
    availableNorm.set(id, id);
    availableNorm.set(normalizeGatewayModelId(id), id);
  }
  for (const alias of llmModelIdAliases(requestedModel)) {
    const hit =
      availableNorm.get(alias) ??
      availableNorm.get(normalizeGatewayModelId(alias));
    if (hit) return hit;
  }
  return null;
}

/**
 * Ollama tags look like ``qwen3:8b``; some Internal LLM Gateways register
 * the same model as ``qwen3-8b``. Only rewrite that size-tag shape.
 */
const OLLAMA_SIZE_TAG =
  /^([A-Za-z0-9._]+):(\d+[bB](?:-[A-Za-z0-9._]+)?)$/;
const HYPHEN_SIZE_TAG =
  /^([A-Za-z0-9._]+)-(\d+[bB](?:-[A-Za-z0-9._]+)?)$/;

function llmEndpointPort(baseUrl: string): string | null {
  try {
    const url = new URL(baseUrl);
    if (url.port) return url.port;
    return url.protocol === "https:" ? "443" : "80";
  } catch {
    return null;
  }
}

/**
 * When the browser cannot probe ``/v1/models`` (CORS), keep the user's id
 * style aligned with common LAN gateways: Ollama ``:11434`` prefers
 * ``qwen3:8b``; other private OpenAI gateways often ACL ``qwen3-8b``.
 */
export function applyLanModelIdStyleWhenProbeSkipped(
  llm: Record<string, unknown>,
): void {
  const baseUrl = typeof llm.base_url === "string" ? llm.base_url : "";
  const model = typeof llm.model === "string" ? llm.model : "";
  if (!baseUrl.trim() || !model.trim()) return;
  if (!isPrivateOrLocalLlmEndpoint(baseUrl)) return;

  const port = llmEndpointPort(baseUrl);
  const bare = bareLlmModelId(model);
  if (port === "11434") {
    const m = HYPHEN_SIZE_TAG.exec(bare);
    if (m) {
      llm.model = normalizeLlmModelForLiteLLM(`${m[1]}:${m[2]}`, baseUrl);
    }
    return;
  }

  const m = OLLAMA_SIZE_TAG.exec(bare);
  if (m) {
    llm.model = normalizeLlmModelForLiteLLM(`${m[1]}-${m[2]}`, baseUrl);
  }
}

/** Browser/network failure talking to a custom LLM base_url (often CORS). */
export class LlmEndpointUnreachableError extends Error {
  readonly name = "LlmEndpointUnreachableError";
}

export function isLlmEndpointUnreachableError(
  error: unknown,
): error is LlmEndpointUnreachableError {
  return (
    error instanceof LlmEndpointUnreachableError ||
    (error instanceof Error &&
      (error.name === "LlmEndpointUnreachableError" ||
        error.message.startsWith("Cannot reach LLM endpoint ")))
  );
}

/**
 * List model ids from an OpenAI-compatible ``GET .../models`` endpoint.
 * Rejects HTML (wrong port / SPA) so save fails before chat.
 */
export async function fetchOpenAiCompatibleModelIds(
  baseUrl: string,
  apiKey?: string | null,
  fetchImpl: typeof fetch = fetch,
): Promise<string[]> {
  const root = normalizeOpenAiCompatibleBaseUrl(baseUrl) ?? baseUrl.trim();
  const modelsUrl = root.replace(/\/+$/, "").endsWith("/models")
    ? root.replace(/\/+$/, "")
    : `${root.replace(/\/+$/, "")}/models`;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (apiKey?.trim()) {
    headers.Authorization = `Bearer ${apiKey.trim()}`;
  }

  let response: Response;
  try {
    response = await fetchImpl(modelsUrl, {
      method: "GET",
      headers,
      signal: AbortSignal.timeout(12_000),
    });
  } catch (err) {
    // Mark as unreachable so save can soft-skip: browser CORS / offline
    // hosts throw TypeError("Failed to fetch") even when the API key is valid
    // for server-side calls from the agent-server.
    throw new LlmEndpointUnreachableError(
      `Cannot reach LLM endpoint ${modelsUrl}: ${
        err instanceof Error ? err.message : String(err)
      }`,
    );
  }

  const contentType = response.headers.get("content-type") ?? "";
  const bodyText = await response.text();
  if (
    contentType.includes("text/html") ||
    /^\s*<!doctype html/i.test(bodyText) ||
    /^\s*<html/i.test(bodyText)
  ) {
    throw new Error(
      `LLM base URL ${root} returned HTML instead of OpenAI /v1/models JSON. ` +
        `Check the host/port (Ollama is usually :11434/v1).`,
    );
  }

  if (!response.ok) {
    throw new Error(
      `LLM /v1/models failed (${response.status}) at ${modelsUrl}: ${bodyText.slice(0, 200)}`,
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(bodyText);
  } catch {
    throw new Error(
      `LLM /v1/models at ${modelsUrl} is not JSON: ${bodyText.slice(0, 120)}`,
    );
  }

  const data = (parsed as { data?: unknown }).data;
  if (!Array.isArray(data)) {
    throw new Error(
      `LLM /v1/models at ${modelsUrl} missing data[]; got: ${bodyText.slice(0, 120)}`,
    );
  }

  return data
    .map((row) =>
      row && typeof row === "object" && typeof (row as { id?: unknown }).id === "string"
        ? (row as { id: string }).id
        : null,
    )
    .filter((id): id is string => Boolean(id));
}

/**
 * Ensure the profile model exists on the gateway. Unambiguous aliases
 * (hyphen ↔ colon) are rewritten onto ``llm.model`` as ``openai/<id>``.
 */
export async function assertAndResolveLlmModelOnEndpoint(
  llm: Record<string, unknown>,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  const baseUrl = typeof llm.base_url === "string" ? llm.base_url : null;
  const model = typeof llm.model === "string" ? llm.model : "";
  if (!baseUrl?.trim() || !model.trim()) return;
  // Only probe custom / LAN endpoints — hosted providers use huge catalogs.
  if (
    llmEndpointSupportsOpenAiStreamOptions(baseUrl) &&
    !isPrivateOrLocalLlmEndpoint(baseUrl)
  ) {
    return;
  }

  const apiKey = typeof llm.api_key === "string" ? llm.api_key : null;
  let available: string[];
  try {
    available = await fetchOpenAiCompatibleModelIds(
      baseUrl,
      apiKey,
      fetchImpl,
    );
  } catch (error) {
    // Cross-origin LAN gateways (e.g. :18083) often omit CORS. The probe runs
    // in the browser and fails with Failed to fetch even when the key works
    // from the agent-server. Soft-skip so Save can persist the profile.
    if (isLlmEndpointUnreachableError(error)) {
      applyLanModelIdStyleWhenProbeSkipped(llm);
      return;
    }
    throw error;
  }
  if (available.length === 0) {
    throw new Error(
      `LLM endpoint ${baseUrl} returned an empty model list. Cannot save profile.`,
    );
  }

  const match = findGatewayModelMatch(model, available);
  if (!match) {
    const sample = available.slice(0, 12).join(", ");
    throw new Error(
      `Model "${bareLlmModelId(model)}" is not on ${baseUrl}. ` +
        `Available: ${sample}${available.length > 12 ? ", …" : ""}. ` +
        `Copy an id exactly from that list (hyphen or colon — gateways differ).`,
    );
  }

  llm.model = normalizeLlmModelForLiteLLM(match, baseUrl);
}

export function getUnsupportedLlmProfileReason(
  model: string,
  baseUrl?: string | null,
): string | null {
  const trimmedModel = model.trim();
  if (!trimmedModel) return "LLM profile has no model.";

  const host = (() => {
    if (!baseUrl?.trim()) return "";
    try {
      return new URL(baseUrl).hostname.toLowerCase();
    } catch {
      return baseUrl.toLowerCase();
    }
  })();

  if (
    UNSUPPORTED_LLM_HOST_MARKERS.some((marker) => host.includes(marker)) ||
    UNSUPPORTED_BARE_MODELS.has(trimmedModel.toLowerCase())
  ) {
    return (
      `LLM profile model "${trimmedModel}" is not usable with LiteLLM` +
      (host ? ` (base URL host: ${host})` : "") +
      `. Use a provider-prefixed OpenAI-compatible model such as ` +
      `openai/nemotron-3-nano:4b. Cursor product models (auto) are not supported.`
    );
  }

  if (!hasLlmProviderPrefix(trimmedModel) && !baseUrl?.trim()) {
    return (
      `LLM model "${trimmedModel}" is missing a provider prefix. ` +
      `Pass e.g. openai/${trimmedModel}.`
    );
  }

  return null;
}

export function assertLlmProfileCompatibleWithLiteLLM(
  model: string,
  baseUrl?: string | null,
): void {
  const reason = getUnsupportedLlmProfileReason(model, baseUrl);
  if (reason) throw new Error(reason);
}
