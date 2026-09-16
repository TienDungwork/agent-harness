import { isVmsChartPayload, type VmsChartPayload } from "./types";

/**
 * Extract chart payload from MCP tool observation text (JSON with chart + reply_vi).
 */
export function parseVmsChartFromObservationText(
  text: string,
): VmsChartPayload | null {
  const trimmed = text.trim();
  if (!trimmed) return null;

  // Prefer fenced / raw JSON object containing "chart"
  const candidates: string[] = [];
  if (trimmed.startsWith("{")) candidates.push(trimmed);

  const fence = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence?.[1]) candidates.push(fence[1].trim());

  const embedded = trimmed.match(/\{[\s\S]*"chart"\s*:[\s\S]*\}/);
  if (embedded?.[0]) candidates.push(embedded[0]);

  for (const raw of candidates) {
    try {
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      if (isVmsChartPayload(parsed.chart)) return parsed.chart;
      if (isVmsChartPayload(parsed)) return parsed;
    } catch {
      // try next
    }
  }
  return null;
}

export function isVmsAnalyticsToolName(toolName: string | undefined): boolean {
  if (!toolName) return false;
  const name = toolName.toLowerCase();
  return (
    name === "vms_query" ||
    name.endsWith("__vms_query") ||
    name.includes("vms_query") ||
    name.startsWith("vms_") ||
    name.includes("vms_count") ||
    name.includes("vms_plate") ||
    name.includes("vms_intrusion")
  );
}
