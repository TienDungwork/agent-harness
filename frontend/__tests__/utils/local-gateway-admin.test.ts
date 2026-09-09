import { describe, expect, it, vi } from "vitest";
import { toOrgConversationRow } from "#/api/local-gateway-admin.api";
import {
  isLocalGatewayAdmin,
  LOCAL_GATEWAY_ORG_ID,
} from "#/utils/local-gateway-admin";

describe("local gateway admin helpers", () => {
  it("treats true and 1 as enabled", () => {
    vi.stubEnv("VITE_LOCAL_GATEWAY_ADMIN", "true");
    expect(isLocalGatewayAdmin()).toBe(true);
    vi.stubEnv("VITE_LOCAL_GATEWAY_ADMIN", "1");
    expect(isLocalGatewayAdmin()).toBe(true);
    vi.stubEnv("VITE_LOCAL_GATEWAY_ADMIN", "false");
    expect(isLocalGatewayAdmin()).toBe(false);
    vi.unstubAllEnvs();
  });

  it("keeps a stable synthetic org id", () => {
    expect(LOCAL_GATEWAY_ORG_ID).toBe("local");
  });

  it("maps agent-server search items to org conversation rows", () => {
    const row = toOrgConversationRow({
      id: "abc",
      title: "VMS query",
      created_at: "2026-09-08T00:00:00Z",
      updated_at: "2026-09-08T01:00:00Z",
      execution_status: "running",
      metrics: {
        accumulated_cost: 1.5,
        accumulated_token_usage: {
          prompt_tokens: 10,
          completion_tokens: 5,
        },
      },
      agent: { kind: "Agent", llm: { model: "test-model" } },
    });
    expect(row.id).toBe("abc");
    expect(row.llm_model).toBe("test-model");
    expect(row.total_tokens).toBe(15);
    expect(row.accumulated_cost).toBe(1.5);
  });
});
