import { describe, expect, it } from "vitest";
import {
  API_DEFAULT_AGENT_KIND,
  UI_DEFAULT_AGENT_KIND,
  fromApiAgentKind,
  isDefaultAgentKind,
  toApiAgentKind,
} from "./agent-kind";

describe("agent-kind wire mapping", () => {
  it("maps UI/legacy kinds to openhands for agent-server", () => {
    expect(API_DEFAULT_AGENT_KIND).toBe("openhands");
    expect(toApiAgentKind("Creanova")).toBe("openhands");
    expect(toApiAgentKind("openhands")).toBe("openhands");
    expect(toApiAgentKind("llm")).toBe("openhands");
    expect(toApiAgentKind("acp")).toBe("acp");
  });

  it("maps agent-server openhands back to Creanova for UI", () => {
    expect(UI_DEFAULT_AGENT_KIND).toBe("Creanova");
    expect(fromApiAgentKind("openhands")).toBe("Creanova");
    expect(fromApiAgentKind("Creanova")).toBe("Creanova");
    expect(fromApiAgentKind("llm")).toBe("Creanova");
    expect(fromApiAgentKind("acp")).toBe("acp");
  });

  it("treats Creanova/openhands/llm as the default agent kind", () => {
    expect(isDefaultAgentKind("Creanova")).toBe(true);
    expect(isDefaultAgentKind("openhands")).toBe(true);
    expect(isDefaultAgentKind("llm")).toBe(true);
    expect(isDefaultAgentKind("acp")).toBe(false);
  });
});
