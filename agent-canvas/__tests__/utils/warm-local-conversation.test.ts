import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  claimWarmLocalConversation,
  discardWarmLocalConversation,
  ensureWarmLocalConversation,
  peekWarmLocalConversation,
  resetWarmLocalConversationForTests,
} from "#/utils/warm-local-conversation";

describe("warm-local-conversation", () => {
  beforeEach(() => {
    resetWarmLocalConversationForTests();
  });

  it("stores a ready conversation and claims it once", async () => {
    const createFn = vi.fn().mockResolvedValue({
      conversation_id: "c1",
      session_api_key: null,
      url: null,
    });
    ensureWarmLocalConversation(createFn);
    await vi.waitFor(() => {
      expect(peekWarmLocalConversation()?.conversation_id).toBe("c1");
    });
    expect(createFn).toHaveBeenCalledTimes(1);

    const claimed = await claimWarmLocalConversation();
    expect(claimed?.conversation_id).toBe("c1");
    expect(peekWarmLocalConversation()).toBeNull();
    expect(await claimWarmLocalConversation()).toBeNull();
  });

  it("awaits an in-flight create on claim", async () => {
    let resolveCreate!: (value: {
      conversation_id: string;
      session_api_key: null;
      url: null;
    }) => void;
    const createFn = vi.fn(
      () =>
        new Promise<{
          conversation_id: string;
          session_api_key: null;
          url: null;
        }>((resolve) => {
          resolveCreate = resolve;
        }),
    );
    ensureWarmLocalConversation(createFn);
    const claimPromise = claimWarmLocalConversation();
    resolveCreate({
      conversation_id: "c2",
      session_api_key: null,
      url: null,
    });
    await expect(claimPromise).resolves.toMatchObject({
      conversation_id: "c2",
    });
  });

  it("ignores discarded in-flight creates", async () => {
    let resolveFirst!: (value: {
      conversation_id: string;
      session_api_key: null;
      url: null;
    }) => void;
    const first = vi.fn(
      () =>
        new Promise<{
          conversation_id: string;
          session_api_key: null;
          url: null;
        }>((resolve) => {
          resolveFirst = resolve;
        }),
    );
    ensureWarmLocalConversation(first);
    discardWarmLocalConversation();
    const second = vi.fn().mockResolvedValue({
      conversation_id: "c-new",
      session_api_key: null,
      url: null,
    });
    ensureWarmLocalConversation(second);
    resolveFirst({
      conversation_id: "c-stale",
      session_api_key: null,
      url: null,
    });
    await vi.waitFor(() => {
      expect(peekWarmLocalConversation()?.conversation_id).toBe("c-new");
    });
    expect(peekWarmLocalConversation()?.conversation_id).not.toBe("c-stale");
  });
});
