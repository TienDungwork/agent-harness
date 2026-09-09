import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveLocalGatewayBaseUrl } from "#/api/local-gateway-base-url";

describe("resolveLocalGatewayBaseUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("prefers the page origin when no env base is configured", () => {
    vi.stubEnv("VITE_LOCAL_AUTH_BASE_URL", "");
    vi.stubEnv("VITE_BACKEND_BASE_URL", "");

    expect(resolveLocalGatewayBaseUrl()).toBe("http://localhost:3000");
  });

  it("honors VITE_LOCAL_AUTH_BASE_URL when set", () => {
    vi.stubEnv(
      "VITE_LOCAL_AUTH_BASE_URL",
      "https://gateway.example.test/",
    );
    vi.stubEnv("VITE_BACKEND_BASE_URL", "http://192.168.1.10:18010");

    expect(resolveLocalGatewayBaseUrl()).toBe("https://gateway.example.test");
  });

  it("uses the page origin when baked backend host differs from the browser", () => {
    vi.stubEnv("VITE_LOCAL_AUTH_BASE_URL", "");
    vi.stubEnv("VITE_BACKEND_BASE_URL", "http://192.168.1.191:18010");

    expect(resolveLocalGatewayBaseUrl()).toBe("http://localhost:3000");
  });

  it("uses the page origin when loopback env port differs from the browser", () => {
    vi.stubEnv("VITE_LOCAL_AUTH_BASE_URL", "");
    vi.stubEnv("VITE_BACKEND_BASE_URL", "http://127.0.0.1:18010");

    expect(resolveLocalGatewayBaseUrl()).toBe("http://localhost:3000");
  });
});
