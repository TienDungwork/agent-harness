import { CreanovaAction } from "#/types/core/actions";
import { CreanovaEventType } from "#/types/core/base";
import {
  isCommandAction,
  isCommandObservation,
  isCreanovaAction,
  isCreanovaObservation,
} from "#/types/core/guards";
import { CreanovaObservation } from "#/types/core/observations";

const COMMON_NO_RENDER_LIST: CreanovaEventType[] = [
  "system",
  "agent_state_changed",
  "change_agent_state",
];

const ACTION_NO_RENDER_LIST: CreanovaEventType[] = ["recall"];

const OBSERVATION_NO_RENDER_LIST: CreanovaEventType[] = ["think"];

export const shouldRenderEvent = (
  event: CreanovaAction | CreanovaObservation,
) => {
  if (isCreanovaAction(event)) {
    if (isCommandAction(event) && event.source === "user") {
      // For user commands, we always hide them from the chat interface
      return false;
    }

    const noRenderList = COMMON_NO_RENDER_LIST.concat(ACTION_NO_RENDER_LIST);
    return !noRenderList.includes(event.action);
  }

  if (isCreanovaObservation(event)) {
    if (isCommandObservation(event) && event.source === "user") {
      // For user commands, we always hide them from the chat interface
      return false;
    }

    const noRenderList = COMMON_NO_RENDER_LIST.concat(
      OBSERVATION_NO_RENDER_LIST,
    );
    return !noRenderList.includes(event.observation);
  }

  return true;
};

export const hasUserEvent = (
  events: (CreanovaAction | CreanovaObservation)[],
) => events.some((event) => isCreanovaAction(event) && event.source === "user");
