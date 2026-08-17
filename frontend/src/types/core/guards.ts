import { CreanovaParsedEvent } from ".";
import {
  UserMessageAction,
  AssistantMessageAction,
  CreanovaAction,
  SystemMessageAction,
  CommandAction,
  FinishAction,
  TaskTrackingAction,
} from "./actions";
import {
  AgentStateChangeObservation,
  CommandObservation,
  ErrorObservation,
  MCPObservation,
  CreanovaObservation,
  TaskTrackingObservation,
} from "./observations";
import { StatusUpdate } from "./variances";

export const isCreanovaEvent = (event: unknown): event is CreanovaParsedEvent =>
  typeof event === "object" &&
  event !== null &&
  "id" in event &&
  "source" in event &&
  "message" in event &&
  "timestamp" in event;

export const isCreanovaAction = (
  event: CreanovaParsedEvent,
): event is CreanovaAction => "action" in event;

export const isCreanovaObservation = (
  event: CreanovaParsedEvent,
): event is CreanovaObservation => "observation" in event;

export const isUserMessage = (
  event: CreanovaParsedEvent,
): event is UserMessageAction =>
  isCreanovaAction(event) &&
  event.source === "user" &&
  event.action === "message";

export const isAssistantMessage = (
  event: CreanovaParsedEvent,
): event is AssistantMessageAction =>
  isCreanovaAction(event) &&
  event.source === "agent" &&
  (event.action === "message" || event.action === "finish");

export const isErrorObservation = (
  event: CreanovaParsedEvent,
): event is ErrorObservation =>
  isCreanovaObservation(event) && event.observation === "error";

export const isCommandAction = (
  event: CreanovaParsedEvent,
): event is CommandAction => isCreanovaAction(event) && event.action === "run";

export const isAgentStateChangeObservation = (
  event: CreanovaParsedEvent,
): event is AgentStateChangeObservation =>
  isCreanovaObservation(event) && event.observation === "agent_state_changed";

export const isCommandObservation = (
  event: CreanovaParsedEvent,
): event is CommandObservation =>
  isCreanovaObservation(event) && event.observation === "run";

export const isFinishAction = (
  event: CreanovaParsedEvent,
): event is FinishAction =>
  isCreanovaAction(event) && event.action === "finish";

export const isSystemMessage = (
  event: CreanovaParsedEvent,
): event is SystemMessageAction =>
  isCreanovaAction(event) && event.action === "system";

export const isRejectObservation = (
  event: CreanovaParsedEvent,
): event is CreanovaObservation =>
  isCreanovaObservation(event) && event.observation === "user_rejected";

export const isMcpObservation = (
  event: CreanovaParsedEvent,
): event is MCPObservation =>
  isCreanovaObservation(event) && event.observation === "mcp";

export const isTaskTrackingAction = (
  event: CreanovaParsedEvent,
): event is TaskTrackingAction =>
  isCreanovaAction(event) && event.action === "task_tracking";

export const isTaskTrackingObservation = (
  event: CreanovaParsedEvent,
): event is TaskTrackingObservation =>
  isCreanovaObservation(event) && event.observation === "task_tracking";

export const isStatusUpdate = (event: unknown): event is StatusUpdate =>
  typeof event === "object" &&
  event !== null &&
  "status_update" in event &&
  "type" in event &&
  "id" in event;

export const isActionOrObservation = (
  event: CreanovaParsedEvent,
): event is CreanovaAction | CreanovaObservation =>
  isCreanovaAction(event) || isCreanovaObservation(event);
