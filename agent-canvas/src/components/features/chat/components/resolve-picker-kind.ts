export type PickerKind = "model" | "agent-profile" | "llm-profile";

export interface ConversationStartState {
  isLoadingHistory: boolean;
  hasUserEvents: boolean;
  hasPendingUserMessages: boolean;
  hasSubstantiveAgentActions: boolean;
  hasModelEntries: boolean;
}

export function hasConversationStarted({
  isLoadingHistory,
  hasUserEvents,
  hasPendingUserMessages,
  hasSubstantiveAgentActions,
  hasModelEntries,
}: ConversationStartState) {
  return (
    isLoadingHistory ||
    hasUserEvents ||
    hasPendingUserMessages ||
    hasSubstantiveAgentActions ||
    hasModelEntries
  );
}

export interface ResolvePickerKindInput {
  hasConversation: boolean;
  hasStartedConversation?: boolean;
  isCloud: boolean;
  isAcp: boolean;
  profilesAvailable: boolean;
  /** True when a named (non-`default`) AgentProfile exists. */
  hasNamedAgentProfiles?: boolean;
}
export function resolvePickerKind({
  hasConversation,
  hasStartedConversation = hasConversation,
  isCloud,
  isAcp,
  profilesAvailable,
  hasNamedAgentProfiles = false,
}: ResolvePickerKindInput): PickerKind {
  // Home: the seeded `default` AgentProfile is not a model picker. Show LLM
  // profiles so the user can choose a model before the first send.
  // Named AgentProfiles keep the agent-profile picker (#3727).
  if (!hasConversation) {
    if (profilesAvailable && hasNamedAgentProfiles) return "agent-profile";
    return isCloud ? "model" : "llm-profile";
  }
  if (!hasStartedConversation) {
    if (profilesAvailable) return "agent-profile";
    return isCloud ? "model" : "llm-profile";
  }
  return isAcp ? "model" : "llm-profile";
}
