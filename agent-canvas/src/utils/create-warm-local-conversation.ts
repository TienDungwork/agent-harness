import type { AgentKind } from "#/types/settings";
import AgentServerConversationService from "#/api/conversation-service/agent-server-conversation-service.api";
import type { CreateConversationResponse } from "#/hooks/mutation/use-create-conversation";
import {
  discardWarmLocalConversation,
  ensureWarmLocalConversation,
} from "#/utils/warm-local-conversation";

/** Create one empty local conversation the same way Home warm-pool does. */
export async function createWarmLocalConversationResponse(args?: {
  agentProfileId?: string;
  agentProfileKind?: AgentKind;
}): Promise<CreateConversationResponse> {
  const conversation = await AgentServerConversationService.createConversation(
    undefined,
    undefined,
    undefined,
    null,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    args?.agentProfileId,
    args?.agentProfileKind,
  );
  const conversationId = conversation.app_conversation_id
    ? conversation.app_conversation_id
    : `task-${conversation.id}`;
  return {
    conversation_id: conversationId,
    session_api_key: null,
    url: conversation.agent_server_url,
    task_id: conversation.id,
  };
}

export function startWarmLocalConversation(args?: {
  agentProfileId?: string;
  agentProfileKind?: AgentKind;
}): void {
  ensureWarmLocalConversation(() =>
    createWarmLocalConversationResponse(args),
  );
}

export function rewarmLocalConversation(args?: {
  agentProfileId?: string;
  agentProfileKind?: AgentKind;
}): void {
  startWarmLocalConversation(args);
}

export function resetAndWarmLocalConversation(args?: {
  agentProfileId?: string;
  agentProfileKind?: AgentKind;
}): void {
  discardWarmLocalConversation();
  startWarmLocalConversation(args);
}
