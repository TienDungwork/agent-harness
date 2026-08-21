import { describe, expect, it } from "vitest";
import {
  assertLlmProfileCompatibleWithLiteLLM,
  getUnsupportedLlmProfileReason,
  hasLlmProviderPrefix,
  llmModelsMatch,
  normalizeLlmModelForLiteLLM,
} from "./llm-model-wire";

describe("llm-model-wire", () => {
  it("detects provider prefixes", () => {
    expect(hasLlmProviderPrefix("openai/nemotron-3-nano:4b")).toBe(true);
    expect(hasLlmProviderPrefix("nemotron-3-nano:4b")).toBe(false);
    expect(hasLlmProviderPrefix("auto")).toBe(false);
  });

  it("prefixes openai/ when base_url is set and model is bare", () => {
    expect(
      normalizeLlmModelForLiteLLM(
        "nemotron-3-nano:4b",
        "https://example.com/v1",
      ),
    ).toBe("openai/nemotron-3-nano:4b");
    expect(
      normalizeLlmModelForLiteLLM(
        "openai/nemotron-3-nano:4b",
        "https://example.com/v1",
      ),
    ).toBe("openai/nemotron-3-nano:4b");
    expect(normalizeLlmModelForLiteLLM("nemotron-3-nano:4b", null)).toBe(
      "nemotron-3-nano:4b",
    );
  });

  it("matches models with or without openai/ prefix", () => {
    expect(
      llmModelsMatch("openai/nemotron-3-nano:4b", "nemotron-3-nano:4b"),
    ).toBe(true);
    expect(llmModelsMatch("openai/gpt-4o", "anthropic/claude")).toBe(false);
  });

  it("rejects Cursor product models / api.cursor.com for LiteLLM", () => {
    expect(
      getUnsupportedLlmProfileReason("auto", "https://api.cursor.com"),
    ).toMatch(/not usable with LiteLLM/);
    expect(
      getUnsupportedLlmProfileReason(
        "cursorauto",
        "https://api.cursor.com/v1",
      ),
    ).toMatch(/Cursor product models/);
    expect(() =>
      assertLlmProfileCompatibleWithLiteLLM(
        "auto",
        "https://api.cursor.com",
      ),
    ).toThrow(/LiteLLM/);
  });

  it("allows OpenAI-compatible custom endpoints with a prefixed model", () => {
    expect(
      getUnsupportedLlmProfileReason(
        "openai/nemotron-3-nano:4b",
        "https://guides.example.com/v1",
      ),
    ).toBeNull();
  });
});
