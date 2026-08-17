import React from "react";
import { CreanovaAction } from "#/types/core/actions";
import { isCreanovaAction } from "#/types/core/guards";
import { ChatMessage } from "../chat-message";

const hasThoughtProperty = (
  obj: Record<string, unknown>,
): obj is { thought: string } => "thought" in obj && !!obj.thought;

interface ObservationPairEventMessageProps {
  event: CreanovaAction;
}

export function ObservationPairEventMessage({
  event,
}: ObservationPairEventMessageProps) {
  if (!isCreanovaAction(event)) {
    return null;
  }

  if (hasThoughtProperty(event.args) && event.action !== "think") {
    return (
      <div>
        <ChatMessage type="agent" message={event.args.thought} />
      </div>
    );
  }

  return null;
}
