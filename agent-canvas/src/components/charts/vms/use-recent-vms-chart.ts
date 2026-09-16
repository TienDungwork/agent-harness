import { useMemo } from "react";
import { MCPToolObservation } from "#/types/agent-server/core/base/observation";
import {
  isObservationEvent,
  isMessageEvent,
} from "#/types/agent-server/type-guards";
import { useEventStore } from "#/stores/use-event-store";
import {
  isVmsAnalyticsToolName,
  parseVmsChartFromObservationText,
  type VmsChartPayload,
} from "#/components/charts/vms";

/**
 * Chart for the agent MessageEvent that immediately follows a VMS MCP observation
 * (same turn). Avoids re-attaching the chart to later follow-up replies.
 */
export function useRecentVmsChart(
  beforeTimestamp?: string,
): VmsChartPayload | null {
  const uiEvents = useEventStore((state) => state.uiEvents);
  return useMemo(() => {
    // Walk events at/before this message, newest first. First hit should be the
    // VMS observation for this turn; stop at the previous user message.
    for (let i = uiEvents.length - 1; i >= 0; i -= 1) {
      const ev = uiEvents[i];
      if (
        beforeTimestamp &&
        ev.timestamp &&
        ev.timestamp > beforeTimestamp
      ) {
        continue;
      }
      // Skip the message we're rendering (same timestamp / later agent msgs).
      if (
        isMessageEvent(ev) &&
        beforeTimestamp &&
        ev.timestamp === beforeTimestamp
      ) {
        continue;
      }
      if (isMessageEvent(ev) && ev.source === "user") {
        return null;
      }
      if (!isObservationEvent(ev)) continue;
      if (ev.observation.kind !== "MCPToolObservation") continue;
      const obs = ev.observation as MCPToolObservation;
      if (obs.is_error || !isVmsAnalyticsToolName(obs.tool_name)) continue;
      const text = obs.content
        .filter((c) => c.type === "text")
        .map((c) => c.text)
        .join("\n");
      return parseVmsChartFromObservationText(text);
    }
    return null;
  }, [uiEvents, beforeTimestamp]);
}
