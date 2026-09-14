/**
 * Default stdio MCP so agent conversations always see vms_* / infra tools.
 * Script lives on the host bind-mount at /opt/infra-mcp inside agent-canvas.
 */
export const CREANOVA_INFRA_MCP_SERVER_NAME = "creanova_infra";

export function buildCreanovaInfraMcpServerConfig(options?: {
  gatewayUrl?: string;
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

  return {
    command: "uv",
    args: [
      "run",
      "--with",
      "httpx",
      "--with",
      "mcp",
      "python",
      "/opt/infra-mcp/mcp_stdio.py",
    ],
    env: {
      GATEWAY_URL: gatewayUrl,
      // INFRA_AGENT_TOKEN is inherited from agent-server process env
      // (canvas entrypoint exports it).
    },
  };
}

/** Merge default infra MCP into an SDK-shaped mcp_config map if missing. */
export function ensureCreanovaInfraMcpConfig(
  mcpConfig: Record<string, unknown>,
): Record<string, unknown> {
  if (
    CREANOVA_INFRA_MCP_SERVER_NAME in mcpConfig ||
    "creanova-infra" in mcpConfig
  ) {
    return mcpConfig;
  }
  return {
    ...mcpConfig,
    [CREANOVA_INFRA_MCP_SERVER_NAME]: buildCreanovaInfraMcpServerConfig(),
  };
}
