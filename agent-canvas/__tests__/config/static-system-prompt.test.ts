import { describe, expect, it } from "vitest";

import {
  CANVAS_PROMPT_MANIFEST,
  CANVAS_STATIC_PROMPT_SECTIONS,
  assembleCanvasStaticSystemPrompt,
  isCanvasPromptSectionEnabled,
} from "#/config/static-system-prompt";

describe("assembleCanvasStaticSystemPrompt", () => {
  it("joins enabled sections including Canvas SOUL.md when not LAN", () => {
    const prompt = assembleCanvasStaticSystemPrompt({ enableBrowser: true });
    expect(prompt).toContain("<SOUL>");
    expect(prompt).toContain("You are Creanova, a local AI software engineer");
    expect(prompt).toContain("<ROLE>");
    expect(prompt).toContain("<SECURITY_RISK_ASSESSMENT>");
    expect(prompt).toContain("<BROWSER_TOOLS>");
    expect(prompt).toContain("<PROCESS_MANAGEMENT>");
    expect(prompt).not.toContain("<EXTERNAL_SERVICES>");
    expect(CANVAS_STATIC_PROMPT_SECTIONS).toHaveLength(6);
  });

  it("omits BROWSER_TOOLS when the browser toolset is off", () => {
    const prompt = assembleCanvasStaticSystemPrompt({ enableBrowser: false });
    expect(prompt).not.toContain("<BROWSER_TOOLS>");
    expect(prompt).toContain("<ROLE>");
  });

  it("drops lan_disable sections for a LAN endpoint", () => {
    const prompt = assembleCanvasStaticSystemPrompt({
      enableBrowser: true,
      isLan: true,
    });
    expect(prompt).toContain("<SOUL>");
    expect(prompt).toContain("<ROLE>");
    expect(prompt).not.toContain("<PROCESS_MANAGEMENT>");
    expect(prompt).not.toContain("<SECURITY_RISK_ASSESSMENT>");
    expect(prompt).not.toContain("<BROWSER_TOOLS>");
  });
});

describe("isCanvasPromptSectionEnabled", () => {
  it("honors the switchboard enabled flag", () => {
    const soul = CANVAS_PROMPT_MANIFEST.sections.find(
      (section) => section.id === "soul",
    );
    expect(soul?.enabled).toBe(true);
    expect(
      isCanvasPromptSectionEnabled("soul", { isLan: false }),
    ).toBe(true);
    expect(
      isCanvasPromptSectionEnabled("external_services", { isLan: false }),
    ).toBe(false);
  });

  it("keeps harness on LAN and drops runtime_services on LAN", () => {
    expect(
      isCanvasPromptSectionEnabled("harness", { isLan: true }),
    ).toBe(true);
    expect(
      isCanvasPromptSectionEnabled("runtime_services", { isLan: true }),
    ).toBe(false);
    expect(
      isCanvasPromptSectionEnabled("runtime_services", { isLan: false }),
    ).toBe(true);
  });
});
