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
