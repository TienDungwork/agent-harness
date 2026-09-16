import { describe, expect, it } from "vitest";

import {
  CREANOVA_INFRA_MCP_SERVER_NAME,
  ensureCreanovaInfraMcpConfig,
  buildCreanovaInfraMcpServerConfig,
  isSlowUvInfraMcpEntry,
} from "#/config/creanova-infra-mcp";

describe("ensureCreanovaInfraMcpConfig", () => {
  it("injects creanova_infra when mcp_config is empty", () => {
    const next = ensureCreanovaInfraMcpConfig({});
    expect(next[CREANOVA_INFRA_MCP_SERVER_NAME]).toEqual(
      buildCreanovaInfraMcpServerConfig(),
    );
  });

  it("does not replace a custom non-uv creanova_infra entry", () => {
    const existing = {
      [CREANOVA_INFRA_MCP_SERVER_NAME]: {
        command: "echo",
        args: ["custom"],
      },
    };
    expect(ensureCreanovaInfraMcpConfig(existing)).toEqual(existing);
  });

  it("replaces legacy uv run --with mcp launcher with python3", () => {
    const existing = {
      [CREANOVA_INFRA_MCP_SERVER_NAME]: {
        command: "uv",
        args: ["run", "--with", "httpx", "--with", "mcp", "python", "/opt/infra-mcp/mcp_stdio.py"],
        env: { GATEWAY_URL: "http://local-gateway:18110" },
      },
      other: { command: "npx", args: ["foo"] },
    };
    const next = ensureCreanovaInfraMcpConfig(existing);
    expect(next.other).toEqual(existing.other);
    expect(next[CREANOVA_INFRA_MCP_SERVER_NAME]).toEqual(
      buildCreanovaInfraMcpServerConfig(),
    );
    expect(isSlowUvInfraMcpEntry(next[CREANOVA_INFRA_MCP_SERVER_NAME])).toBe(
      false,
    );
  });
});
