import React from "react";
import { ActionEvent } from "#/types/agent-server/core";
import { FinishAction } from "#/types/agent-server/core/base/action";
import { ChatMessage } from "../../../features/chat/chat-message";
import { getEventContent } from "../event-content-helpers/get-event-content";
import { CriticResultDisplay } from "./critic-result-display";
import { VmsAnalyticsChartSafe } from "#/components/charts/vms";
import { useRecentVmsChart } from "#/components/charts/vms/use-recent-vms-chart";

interface FinishEventMessageProps {
  event: ActionEvent<FinishAction>;
  isFromPlanningAgent?: boolean;
}

export function FinishEventMessage({
  event,
  isFromPlanningAgent = false,
}: FinishEventMessageProps) {
  const eventContent = getEventContent(event);
  const message =
    typeof eventContent.details === "string"
      ? eventContent.details
      : String(eventContent.details);

  const chart = useRecentVmsChart(event.timestamp);

  return (
    <>
      <ChatMessage
        type="agent"
        message={message}
        isFromPlanningAgent={isFromPlanningAgent}
      />
      {chart ? <VmsAnalyticsChartSafe chart={chart} /> : null}
      {event.critic_result != null && (
        <CriticResultDisplay criticResult={event.critic_result} />
      )}
    </>
  );
}
