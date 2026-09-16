/**
 * Default stdio MCP so agent conversations always see vms_* / infra tools.
 * Script lives on the host bind-mount at /opt/infra-mcp inside agent-canvas.
 *
 * Use system python3 (httpx+mcp already in the image) — avoid `uv run --with`
 * cold-start (~seconds) on every conversation create.
 */
export const CREANOVA_INFRA_MCP_SERVER_NAME = "creanova_infra";

const LEGACY_INFRA_MCP_NAMES = [
  CREANOVA_INFRA_MCP_SERVER_NAME,
  "creanova-infra",
] as const;

export function buildCreanovaInfraMcpServerConfig(options?: {
  gatewayUrl?: string;
  vmsOnly?: boolean;
}): {
  command: string;
  args: string[];
  env: Record<string, string>;
} {
  const gatewayUrl =
    options?.gatewayUrl?.trim() ||
    (typeof process !== "undefined" &&
      typeof process.env?.LOCAL_GATEWAY_URL === "string" &&
      process.env.LOCAL_GATEWAY_URL.trim()) ||
    "http://local-gateway:18110";

  void options?.vmsOnly;

  return {
    command: "python3",
    args: ["/opt/infra-mcp/mcp_stdio.py"],
    env: {
      GATEWAY_URL: gatewayUrl,
      // Fewer MCP tools → faster first tool-call TTFT on local LLMs.
      MCP_VMS_ONLY: "1",
      // INFRA_AGENT_TOKEN is inherited from agent-server process env
      // (canvas entrypoint exports it).
    },
  };
}

/** True when the entry still uses `uv run --with …` (multi-second cold start). */
export function isSlowUvInfraMcpEntry(entry: unknown): boolean {
  if (!entry || typeof entry !== "object") {
    return false;
  }
  const rec = entry as Record<string, unknown>;
  const command = typeof rec.command === "string" ? rec.command : "";
  if (command === "uv" || command === "uvx") {
    return true;
  }
  const args = Array.isArray(rec.args) ? rec.args.map(String) : [];
  return args.includes("--with") && args.some((arg) => arg.includes("mcp"));
}

/**
 * Ensure creanova_infra is present and not the legacy `uv run --with` launcher.
 * Custom non-uv entries are left alone.
 */
export function ensureCreanovaInfraMcpConfig(
  mcpConfig: Record<string, unknown>,
  options?: { vmsOnly?: boolean },
): Record<string, unknown> {
  const fast = buildCreanovaInfraMcpServerConfig(options);
  let next: Record<string, unknown> = mcpConfig;
  let mutated = false;

  const ensureCopy = () => {
    if (!mutated) {
      next = { ...mcpConfig };
      mutated = true;
    }
  };

  for (const name of LEGACY_INFRA_MCP_NAMES) {
    if (!(name in next)) {
      continue;
    }
    if (!isSlowUvInfraMcpEntry(next[name])) {
      continue;
    }
    ensureCopy();
    delete next[name];
  }

  const hasUsableInfra =
    (CREANOVA_INFRA_MCP_SERVER_NAME in next &&
      !isSlowUvInfraMcpEntry(next[CREANOVA_INFRA_MCP_SERVER_NAME])) ||
    ("creanova-infra" in next &&
      !isSlowUvInfraMcpEntry(next["creanova-infra"]));

  if (hasUsableInfra) {
    return next;
  }

  ensureCopy();
  next[CREANOVA_INFRA_MCP_SERVER_NAME] = fast;
  return next;
}
