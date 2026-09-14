import { describe, expect, it, vi } from "vitest";
import {
  applyStrictOpenAiCompatibleLlmGuards,
  assertAndResolveLlmModelOnEndpoint,
  assertLlmProfileCompatibleWithLiteLLM,
  bareLlmModelId,
  findGatewayModelMatch,
  getUnsupportedLlmProfileReason,
  hasLlmProviderPrefix,
  isPrivateOrLocalLlmEndpoint,
  llmEndpointSupportsOpenAiStreamOptions,
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

  it("appends /v1 to OpenAI-compatible host roots", async () => {
    const { normalizeOpenAiCompatibleBaseUrl } = await import("./llm-model-wire");
    expect(
      normalizeOpenAiCompatibleBaseUrl(
        "https://pmid-catering-formed-shop.trycloudflare.com/",
      ),
    ).toBe("https://pmid-catering-formed-shop.trycloudflare.com/v1");
    expect(
      normalizeOpenAiCompatibleBaseUrl(
        "https://pmid-catering-formed-shop.trycloudflare.com/v1",
      ),
    ).toBe("https://pmid-catering-formed-shop.trycloudflare.com/v1");
    expect(normalizeOpenAiCompatibleBaseUrl(null)).toBeNull();
  });

  it("treats LAN OpenAI-compatible gateways as incompatible with stream_options", () => {
    expect(
      llmEndpointSupportsOpenAiStreamOptions("http://192.168.1.196:18083/v1"),
    ).toBe(false);
    expect(
      llmEndpointSupportsOpenAiStreamOptions("https://api.openai.com/v1"),
    ).toBe(true);
    expect(llmEndpointSupportsOpenAiStreamOptions(null)).toBe(true);

    const llm: Record<string, unknown> = {
      base_url: "http://192.168.1.196:18083/v1",
      stream: true,
      reasoning_effort: "high",
      native_tool_calling: true,
    };
    applyStrictOpenAiCompatibleLlmGuards(llm);
    expect(llm.stream).toBe(false);
    expect(llm.reasoning_effort).toBeUndefined();
    expect(llm.force_string_serializer).toBe(true);
    expect(llm.native_tool_calling).toBe(false);
    expect(llm.caching_prompt).toBe(false);
  });

  it("detects private/local LLM endpoints", () => {
    expect(
      isPrivateOrLocalLlmEndpoint("http://192.168.1.196:18083/v1"),
    ).toBe(true);
    expect(isPrivateOrLocalLlmEndpoint("http://10.240.120.2:8000/v1")).toBe(
      true,
    );
    expect(isPrivateOrLocalLlmEndpoint("https://nested.example.com")).toBe(
      false,
    );
    expect(isPrivateOrLocalLlmEndpoint("https://api.openai.com/v1")).toBe(
      false,
    );
  });

  it("matches hyphen/colon gateway model aliases", () => {
    expect(bareLlmModelId("openai/qwen3:4b")).toBe("qwen3:4b");
    expect(findGatewayModelMatch("qwen3-4b", ["qwen3:4b", "qwen3:8b"])).toBe(
      "qwen3:4b",
    );
    expect(findGatewayModelMatch("openai/qwen3:4b", ["qwen3:4b"])).toBe(
      "qwen3:4b",
    );
    expect(findGatewayModelMatch("missing", ["qwen3:4b"])).toBeNull();
  });

  it("resolves LAN model against /v1/models and rewrites aliases", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          data: [{ id: "qwen3:4b" }, { id: "qwen3-16k:latest" }],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const llm: Record<string, unknown> = {
      model: "openai/qwen3-4b",
      base_url: "http://192.168.1.196:11434/v1",
    };
    await assertAndResolveLlmModelOnEndpoint(llm, fetchImpl as typeof fetch);
    expect(llm.model).toBe("openai/qwen3:4b");
    expect(fetchImpl).toHaveBeenCalled();
  });

  it("rejects save when model is not on the gateway", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ data: [{ id: "qwen3:4b" }] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(
      assertAndResolveLlmModelOnEndpoint(
        {
          model: "openai/qwen8b",
          base_url: "http://192.168.1.196:11434/v1",
        },
        fetchImpl as typeof fetch,
      ),
    ).rejects.toThrow(/not on/);
  });

  it("rejects HTML responses that are not OpenAI /v1/models", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response("<!doctype html><html></html>", {
        status: 200,
        headers: { "content-type": "text/html" },
      }),
    );
    await expect(
      assertAndResolveLlmModelOnEndpoint(
        {
          model: "openai/qwen3:4b",
          base_url: "http://192.168.1.196:8080/v1",
        },
        fetchImpl as typeof fetch,
      ),
    ).rejects.toThrow(/HTML/);
  });
});