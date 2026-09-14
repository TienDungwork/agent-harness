/**
 * ProfilesService tests using SDK client mocks.
 *
 * Note: We mock ProfilesClient directly because the SDK's HttpClient uses
 * native fetch that MSW doesn't intercept reliably in Node.js test environments.
 * This approach tests that ProfilesService correctly delegates to ProfilesClient
 * methods and propagates errors from the SDK.
 *
 * For full integration testing, use browser-level tests with MSW.
 */
import { ProfilesClient } from "@Creanova/typescript-client/clients";
import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import ProfilesService from "#/api/profiles-service/profiles-service.api";

// Mock the ProfilesClient from the SDK using vi.hoisted
const {
  mockListProfiles,
  mockGetProfile,
  mockSaveProfile,
  mockDeleteProfile,
  mockRenameProfile,
  mockActivateProfile,
} = vi.hoisted(() => ({
  mockListProfiles: vi.fn(),
  mockGetProfile: vi.fn(),
  mockSaveProfile: vi.fn(),
  mockDeleteProfile: vi.fn(),
  mockRenameProfile: vi.fn(),
  mockActivateProfile: vi.fn(),
}));

vi.mock("@Creanova/typescript-client/clients", () => ({
  ProfilesClient: vi.fn(function ProfilesClientMock() {
    return {
      listProfiles: mockListProfiles,
      getProfile: mockGetProfile,
      saveProfile: mockSaveProfile,
      deleteProfile: mockDeleteProfile,
      renameProfile: mockRenameProfile,
      activateProfile: mockActivateProfile,
    };
  }),
}));

vi.mock("#/api/agent-server-client-options", () => ({
  getAgentServerClientOptions: vi.fn(() => ({
    host: "http://localhost:3000",
    apiKey: "test-key",
  })),
}));

describe("ProfilesService", () => {
  beforeEach(() => {
    mockListProfiles.mockReset();
    mockGetProfile.mockReset();
    mockSaveProfile.mockReset();
    mockDeleteProfile.mockReset();
    mockRenameProfile.mockReset();
    mockActivateProfile.mockReset();
    vi.mocked(ProfilesClient).mockClear();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/models")) {
          return new Response(
            JSON.stringify({
              data: [
                { id: "gpt-4" },
                { id: "qwen3:4b" },
                { id: "qwen3-16k" },
              ],
            }),
            {
              status: 200,
              headers: { "content-type": "application/json" },
            },
          );
        }
        return new Response("not found", { status: 404 });
      }),
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  describe("listProfiles", () => {
    it("calls listProfiles and returns profiles list", async () => {
      const mockResponse = {
        profiles: [
          {
            name: "gpt-4-profile",
            model: "openai/gpt-4",
            base_url: null,
            api_key_set: true,
          },
          {
            name: "claude-profile",
            model: "anthropic/claude-3",
            base_url: "https://api.anthropic.com",
            api_key_set: false,
          },
        ],
        active_profile: null,
      };

      mockListProfiles.mockResolvedValue(mockResponse);

      const result = await ProfilesService.listProfiles();

      expect(mockListProfiles).toHaveBeenCalled();
      expect(result).toEqual(mockResponse);
      expect(result.profiles).toHaveLength(2);
    });

    it("returns empty profiles array when no profiles exist", async () => {
      const mockResponse = { profiles: [], active_profile: null };
      mockListProfiles.mockResolvedValue(mockResponse);

      const result = await ProfilesService.listProfiles();

      expect(result.profiles).toEqual([]);
    });

    it("propagates errors from the SDK", async () => {
      mockListProfiles.mockRejectedValue(new Error("Network error"));

      await expect(ProfilesService.listProfiles()).rejects.toThrow(
        "Network error",
      );
    });
  });

  describe("getProfile", () => {
    it("calls getProfile with profile name", async () => {
      const mockResponse = {
        name: "my-profile",
        config: { model: "openai/gpt-4" },
        api_key_set: true,
      };

      mockGetProfile.mockResolvedValue(mockResponse);

      const result = await ProfilesService.getProfile("my-profile");

      expect(mockGetProfile).toHaveBeenCalledWith("my-profile", {});
      expect(result).toEqual(mockResponse);
    });

    it("passes exposeSecrets option when set", async () => {
      const mockResponse = {
        name: "my-profile",
        config: { model: "openai/gpt-4", api_key: "encrypted_..." },
        api_key_set: true,
      };

      mockGetProfile.mockResolvedValue(mockResponse);

      await ProfilesService.getProfile("my-profile", "encrypted");

      expect(mockGetProfile).toHaveBeenCalledWith("my-profile", {
        exposeSecrets: "encrypted",
      });
    });
  });

  describe("saveProfile", () => {
    it("calls saveProfile with name and request body", async () => {
      const mockResponse = { name: "new-profile", message: "Profile saved" };
      mockSaveProfile.mockResolvedValue(mockResponse);

      const request = {
        llm: {
          model: "openai/gpt-4",
          api_key: "sk-xxx",
        },
        include_secrets: true,
      };

      const result = await ProfilesService.saveProfile("new-profile", request);

      expect(mockSaveProfile).toHaveBeenCalledWith("new-profile", request);
      expect(result).toEqual(mockResponse);
    });

    it("saves profile with base_url", async () => {
      const mockResponse = { name: "custom-profile", message: "Profile saved" };
      mockSaveProfile.mockResolvedValue(mockResponse);

      const request = {
        llm: {
          model: "openai/gpt-4",
          base_url: "https://custom.api.com",
        },
      };

      await ProfilesService.saveProfile("custom-profile", request);

      expect(mockSaveProfile).toHaveBeenCalledWith("custom-profile", {
        llm: {
          model: "openai/gpt-4",
          base_url: "https://custom.api.com/v1",
          stream: false,
        },
      });
    });

    it("prefixes a LAN Ollama model and drops hosted thinking params", async () => {
      mockSaveProfile.mockResolvedValue({
        name: "qw",
        message: "Profile saved",
      });

      await ProfilesService.saveProfile("qw", {
        llm: {
          model: "qwen3-16k",
          base_url: "http://192.168.1.196:11434/v1",
          stream: true,
          reasoning_effort: "high",
          extended_thinking_budget: 200000,
        },
      });

      expect(mockSaveProfile).toHaveBeenCalledWith("qw", {
        llm: {
          model: "openai/qwen3-16k",
          base_url: "http://192.168.1.196:11434/v1",
          stream: false,
          force_string_serializer: true,
          native_tool_calling: false,
          caching_prompt: false,
        },
      });
    });

    it("rewrites qwen3-4b to qwen3:4b when the gateway only lists the colon id", async () => {
      mockSaveProfile.mockResolvedValue({
        name: "ntiendung",
        message: "Profile saved",
      });

      await ProfilesService.saveProfile("ntiendung", {
        llm: {
          model: "qwen3-4b",
          base_url: "http://192.168.1.196:11434/v1",
        },
      });

      expect(mockSaveProfile).toHaveBeenCalledWith(
        "ntiendung",
        expect.objectContaining({
          llm: expect.objectContaining({
            model: "openai/qwen3:4b",
            base_url: "http://192.168.1.196:11434/v1",
          }),
        }),
      );
    });

    it("blocks save when the model is not on the gateway", async () => {
      await expect(
        ProfilesService.saveProfile("bad", {
          llm: {
            model: "qwen8b",
            base_url: "http://192.168.1.196:11434/v1",
          },
        }),
      ).rejects.toThrow(/not on/);
      expect(mockSaveProfile).not.toHaveBeenCalled();
    });
  });

  describe("deleteProfile", () => {
    it("calls deleteProfile with profile name", async () => {
      const mockResponse = { name: "old-profile", message: "Profile deleted" };
      mockDeleteProfile.mockResolvedValue(mockResponse);

      const result = await ProfilesService.deleteProfile("old-profile");

      expect(mockDeleteProfile).toHaveBeenCalledWith("old-profile");
      expect(result).toEqual(mockResponse);
    });
  });

  describe("renameProfile", () => {
    it("calls renameProfile with old and new names", async () => {
      const mockResponse = {
        name: "renamed-profile",
        message: "Profile renamed",
      };
      mockRenameProfile.mockResolvedValue(mockResponse);

      const result = await ProfilesService.renameProfile(
        "old-name",
        "renamed-profile",
      );

      expect(mockRenameProfile).toHaveBeenCalledWith(
        "old-name",
        "renamed-profile",
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("activateProfile", () => {
    it("calls activateProfile with profile name", async () => {
      const mockResponse = {
        name: "active-profile",
        message: "Profile activated",
        llm_applied: true,
      };
      mockActivateProfile.mockResolvedValue(mockResponse);

      const result = await ProfilesService.activateProfile("active-profile");

      expect(mockActivateProfile).toHaveBeenCalledWith("active-profile");
      expect(result).toEqual(mockResponse);
    });
  });
});
