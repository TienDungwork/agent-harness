import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import React from "react";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useSaveLlmProfile } from "#/hooks/mutation/use-save-llm-profile";
import ProfilesService from "#/api/profiles-service/profiles-service.api";
import SettingsService from "#/api/settings-service/settings-service.api";
import { LLM_PROFILES_QUERY_KEYS, SETTINGS_QUERY_KEYS } from "#/hooks/query/query-keys";
import {
  __resetActiveStoreForTests,
  setActiveSelection,
  setRegisteredBackends,
} from "#/api/backend-registry/active-store";
import { ActiveBackendProvider } from "#/contexts/active-backend-context";
import type { Backend } from "#/api/backend-registry/types";

vi.mock("#/api/profiles-service/profiles-service.api");
vi.mock("#/api/settings-service/settings-service.api");

const localBackend: Backend = {
  id: "local-1",
  name: "Local 1",
  host: "http://localhost:8000",
  apiKey: "session-key",
  kind: "local",
};

describe("useSaveLlmProfile", () => {
  let queryClient: QueryClient;
  let wrapper: ({ children }: { children: React.ReactNode }) => React.ReactElement;

  beforeEach(() => {
    __resetActiveStoreForTests();
    setRegisteredBackends([localBackend]);
    setActiveSelection({ backendId: localBackend.id, orgId: null });

    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(
        QueryClientProvider,
        { client: queryClient },
        React.createElement(ActiveBackendProvider, null, children),
      );
  });

  afterEach(() => {
    queryClient.clear();
    vi.clearAllMocks();
    __resetActiveStoreForTests();
  });

  it("calls ProfilesService.saveProfile with name and request", async () => {
    vi.mocked(ProfilesService.saveProfile).mockResolvedValue({
      name: "my-profile",
      message: "Profile saved",
    });

    const { result } = renderHook(() => useSaveLlmProfile(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        name: "my-profile",
        request: {
          llm: {
            model: "openai/gpt-4",
            api_key: "sk-xxx",
          },
        },
      });
    });

    expect(ProfilesService.saveProfile).toHaveBeenCalledWith("my-profile", {
      llm: {
        model: "openai/gpt-4",
        api_key: "sk-xxx",
      },
    });
  });

  it("saves profile with include_secrets flag", async () => {
    vi.mocked(ProfilesService.saveProfile).mockResolvedValue({
      name: "snapshot-profile",
      message: "Profile saved",
    });

    const { result } = renderHook(() => useSaveLlmProfile(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        name: "snapshot-profile",
        request: {
          llm: { model: "openai/gpt-4" },
          include_secrets: true,
        },
      });
    });

    expect(ProfilesService.saveProfile).toHaveBeenCalledWith("snapshot-profile", {
      llm: { model: "openai/gpt-4" },
      include_secrets: true,
    });
  });

  it("invalidates all relevant caches on success", async () => {
    vi.mocked(ProfilesService.saveProfile).mockResolvedValue({
      name: "test-profile",
      message: "Profile saved",
    });

    // Pre-populate the profiles cache
    queryClient.setQueryData(
      [...LLM_PROFILES_QUERY_KEYS.all, localBackend.id, null],
      { profiles: [], active_profile: null },
    );
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const invalidateCacheSpy = vi.spyOn(SettingsService, "invalidateCache");

    const { result } = renderHook(() => useSaveLlmProfile(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        name: "test-profile",
        request: { llm: { model: "openai/gpt-4" } },
      });
    });

    // Verifies all three cache invalidations occur on success
    expect(invalidateCacheSpy).toHaveBeenCalled();
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: LLM_PROFILES_QUERY_KEYS.all,
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: SETTINGS_QUERY_KEYS.personal(),
    });
  });

  it("updates the active backend cache immediately with the saved profile", async () => {
    vi.mocked(ProfilesService.saveProfile).mockResolvedValue({
      name: "c",
      message: "Profile saved",
    });

    queryClient.setQueryData(
      [...LLM_PROFILES_QUERY_KEYS.all, localBackend.id, null],
      {
        profiles: [
          {
            name: "nemotron-3-nano-4b",
            model: "openai/nemotron-3-nano:4b",
            base_url: "https://example.com/v1",
            api_key_set: true,
          },
        ],
        active_profile: "nemotron-3-nano-4b",
      },
    );

    const { result } = renderHook(() => useSaveLlmProfile(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        name: "c",
        request: {
          llm: {
            model: "cursorauto",
            base_url: "https://api.cursor.com",
            api_key: "crsr_secret",
          },
          include_secrets: true,
        },
      });
    });

    expect(
      queryClient.getQueryData([
        ...LLM_PROFILES_QUERY_KEYS.all,
        localBackend.id,
        null,
      ]),
    ).toEqual({
      profiles: [
        {
          name: "c",
          model: "cursorauto",
          base_url: "https://api.cursor.com",
          api_key_set: true,
        },
        {
          name: "nemotron-3-nano-4b",
          model: "openai/nemotron-3-nano:4b",
          base_url: "https://example.com/v1",
          api_key_set: true,
        },
      ],
      active_profile: "nemotron-3-nano-4b",
    });
  });

  it("handles save errors", async () => {
    const error = new Error("Profile name already exists");
    vi.mocked(ProfilesService.saveProfile).mockRejectedValue(error);

    const { result } = renderHook(() => useSaveLlmProfile(), { wrapper });

    await expect(
      act(async () => {
        await result.current.mutateAsync({
          name: "duplicate-name",
          request: { llm: { model: "openai/gpt-4" } },
        });
      }),
    ).rejects.toThrow("Profile name already exists");

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});
