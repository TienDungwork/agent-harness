import { useMutation, useQueryClient } from "@tanstack/react-query";
import ProfilesService, {
  type ProfileListResponse,
  type SaveProfileRequest,
} from "#/api/profiles-service/profiles-service.api";
import SettingsService from "#/api/settings-service/settings-service.api";
import { useActiveBackend } from "#/contexts/active-backend-context";
import {
  LLM_PROFILES_QUERY_KEYS,
  SETTINGS_QUERY_KEYS,
} from "#/hooks/query/query-keys";

interface SaveLlmProfileVariables {
  name: string;
  request: SaveProfileRequest;
}

export function useSaveLlmProfile() {
  const queryClient = useQueryClient();
  const { backend, orgId } = useActiveBackend();

  return useMutation({
    mutationFn: ({ name, request }: SaveLlmProfileVariables) =>
      ProfilesService.saveProfile(name, request),
    onSuccess: async (_response, { name, request }) => {
      const llm = request.llm as Record<string, unknown>;
      const profileSummary = {
        name,
        model: typeof llm.model === "string" ? llm.model : null,
        base_url: typeof llm.base_url === "string" ? llm.base_url : null,
        api_key_set:
          request.include_secrets !== false &&
          typeof llm.api_key === "string" &&
          llm.api_key.trim().length > 0,
      };

      queryClient.setQueryData<ProfileListResponse | undefined>(
        [...LLM_PROFILES_QUERY_KEYS.all, backend.id, orgId],
        (current) => {
          if (!current) return current;

          const otherProfiles = current.profiles.filter(
            (profile) => profile.name !== name,
          );

          return {
            ...current,
            profiles: [...otherProfiles, profileSummary].sort((a, b) =>
              a.name.localeCompare(b.name),
            ),
          };
        },
      );

      // Invalidate SettingsService internal cache to ensure fresh settings
      // for new conversations (especially if saving the active profile)
      SettingsService.invalidateCache();
      await queryClient.invalidateQueries({
        queryKey: LLM_PROFILES_QUERY_KEYS.all,
      });
      // Use personal() scope for consistency with other settings hooks
      await queryClient.invalidateQueries({
        queryKey: SETTINGS_QUERY_KEYS.personal(),
      });
    },
    // Consumers handle errors with try-catch and manual toasts; disable global toast
    meta: { disableToast: true },
  });
}
