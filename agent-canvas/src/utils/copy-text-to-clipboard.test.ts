/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { copyTextToClipboard } from "#/utils/copy-text-to-clipboard";

describe("copyTextToClipboard", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uses the Clipboard API when available", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.spyOn(navigator.clipboard, "writeText").mockImplementation(writeText);

    await copyTextToClipboard("hello");

    expect(writeText).toHaveBeenCalledWith("hello");
  });

  it("falls back to execCommand when the Clipboard API is blocked", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    vi.spyOn(navigator.clipboard, "writeText").mockImplementation(writeText);
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });

    await copyTextToClipboard("fallback copy");

    expect(writeText).toHaveBeenCalledWith("fallback copy");
    expect(execCommand).toHaveBeenCalledWith("copy");
  });

  it("throws when both clipboard paths fail", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    vi.spyOn(navigator.clipboard, "writeText").mockImplementation(writeText);
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: vi.fn().mockReturnValue(false),
    });

    await expect(copyTextToClipboard("nope")).rejects.toThrow(
      "execCommand copy failed",
    );
  });
});
