import { useEffect, useRef } from "react";
import { useActiveBackend } from "#/contexts/active-backend-context";
import { useLlmConfigured } from "#/hooks/use-llm-configured";
import { useLlmProfiles } from "#/hooks/query/use-llm-profiles";
import { useAgentProfiles } from "#/hooks/query/use-agent-profiles";
import {
  WELL_KNOWN_DEFAULT_AGENT_PROFILE_NAME,
} from "#/api/agent-profiles-service/agent-profiles-service.api";
import type { AgentKind } from "#/types/settings";
import { isLocalAuthEnabled } from "#/api/local-auth/client";
import { discardWarmLocalConversation } from "#/utils/warm-local-conversation";
import {
  createWarmLocalConversationResponse,
  startWarmLocalConversation,
} from "#/utils/create-warm-local-conversation";

function resolveWarmProfileArgs(options: {
  isLocal: boolean;
  activeLlmProfile: string | null;
  activeAgentProfileId: string | null;
  activeAgentProfile:
    | { id: string; name: string; agent_kind: AgentKind }
    | undefined;
}) {
  // Local-auth VMS/SSH stack: never launch via agent_profile_id.
  // Profile resolution injects ~60 public coding skills (~480KB) and blows
  // LiteLLM project message limits. Use lean agent_settings instead.
  if (isLocalAuthEnabled()) {
    const warmKey = `${options.isLocal ? "1" : "0"}:${options.activeLlmProfile ?? ""}:lean`;
    return {
      warmKey,
      warmAgentProfileId: undefined,
      warmAgentProfileKind: undefined,
    };
  }
  const warmAgentProfileId =
    options.activeAgentProfile?.name ===
      WELL_KNOWN_DEFAULT_AGENT_PROFILE_NAME &&
    options.activeAgentProfile.agent_kind === "Creanova"
      ? undefined
      : (options.activeAgentProfileId ?? undefined);
  const warmAgentProfileKind = warmAgentProfileId
    ? options.activeAgentProfile?.agent_kind
    : undefined;
  const warmKey = `${options.isLocal ? "1" : "0"}:${options.activeLlmProfile ?? ""}:${warmAgentProfileId ?? ""}:${warmAgentProfileKind ?? ""}`;
  return { warmKey, warmAgentProfileId, warmAgentProfileKind };
}

/** Actions only — safe to call from Home / sidebar without starting a second prefetch loop. */
export function useWarmLocalConversationActions() {
  const { backend } = useActiveBackend();
  const isLocal = backend.kind === "local";
  const { data: llmProfiles } = useLlmProfiles({ enabled: isLocal });
  const { data: agentProfiles } = useAgentProfiles({ enabled: isLocal });
  const activeAgentProfileId =
    agentProfiles?.active_agent_profile_id ?? null;
  const activeAgentProfile = activeAgentProfileId
    ? agentProfiles?.profiles?.find((p) => p.id === activeAgentProfileId)
    : undefined;
  const { warmAgentProfileId, warmAgentProfileKind } = resolveWarmProfileArgs({
    isLocal,
    activeLlmProfile: llmProfiles?.active_profile ?? null,
    activeAgentProfileId,
    activeAgentProfile: activeAgentProfile
      ? {
          id: activeAgentProfile.id,
          name: activeAgentProfile.name,
          agent_kind: activeAgentProfile.agent_kind,
        }
      : undefined,
  });

  return {
    createWarm: () =>
      createWarmLocalConversationResponse({
        agentProfileId: warmAgentProfileId,
        agentProfileKind: warmAgentProfileKind,
      }),
    rewarm: () =>
      startWarmLocalConversation({
        agentProfileId: warmAgentProfileId,
        agentProfileKind: warmAgentProfileKind,
      }),
  };
}

/**
 * Keep one empty local conversation warm for the whole app shell.
 * Mount ONCE (root-layout). Do not also mount from Home.
 */
export function useWarmLocalConversationPrefetch() {
  const { backend } = useActiveBackend();
  const isLocal = backend.kind === "local";
  const { isConfigured, isLoading } = useLlmConfigured();
  const llmBlocked = !isLoading && !isConfigured;

  const { data: llmProfiles } = useLlmProfiles({ enabled: isLocal });
  const { data: agentProfiles } = useAgentProfiles({ enabled: isLocal });
  const activeLlmProfile = llmProfiles?.active_profile ?? null;
  const activeAgentProfileId =
    agentProfiles?.active_agent_profile_id ?? null;
  const activeAgentProfile = activeAgentProfileId
    ? agentProfiles?.profiles?.find((p) => p.id === activeAgentProfileId)
    : undefined;

  const { warmKey, warmAgentProfileId, warmAgentProfileKind } =
    resolveWarmProfileArgs({
      isLocal,
      activeLlmProfile,
      activeAgentProfileId,
      activeAgentProfile: activeAgentProfile
        ? {
            id: activeAgentProfile.id,
            name: activeAgentProfile.name,
            agent_kind: activeAgentProfile.agent_kind,
          }
        : undefined,
    });

  const warmKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (!isLocal || llmBlocked) {
      if (warmKeyRef.current !== null) {
        discardWarmLocalConversation();
        warmKeyRef.current = null;
      }
      return;
    }
    if (warmKeyRef.current !== warmKey) {
      warmKeyRef.current = warmKey;
      discardWarmLocalConversation();
    }
    startWarmLocalConversation({
      agentProfileId: warmAgentProfileId,
      agentProfileKind: warmAgentProfileKind,
    });
  }, [warmKey, warmAgentProfileId, warmAgentProfileKind, isLocal, llmBlocked]);
}
