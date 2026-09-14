import { describe, expect, it } from "vitest";

import {
  CREANOVA_INFRA_MCP_SERVER_NAME,
  ensureCreanovaInfraMcpConfig,
  buildCreanovaInfraMcpServerConfig,
} from "#/config/creanova-infra-mcp";

describe("ensureCreanovaInfraMcpConfig", () => {
  it("injects creanova_infra when mcp_config is empty", () => {
    const next = ensureCreanovaInfraMcpConfig({});
    expect(next[CREANOVA_INFRA_MCP_SERVER_NAME]).toEqual(
      buildCreanovaInfraMcpServerConfig(),
    );
  });

  it("does not replace an existing creanova_infra entry", () => {
    const existing = {
      [CREANOVA_INFRA_MCP_SERVER_NAME]: {
        command: "echo",
        args: ["custom"],
      },
    };
    expect(ensureCreanovaInfraMcpConfig(existing)).toEqual(existing);
  });
});
