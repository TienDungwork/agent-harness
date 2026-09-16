import { isVmsChartPayload, type VmsChartPayload } from "./types";

const CHART_MARK_RE =
  /<!--CREANOVA_VMS_CHART:([\s\S]*?)-->/g;

/** Strip embedded chart marker from assistant message text for display. */
export function stripVmsChartMarker(text: string): string {
  return text.replace(CHART_MARK_RE, "").trimEnd();
}

/** Chart embedded in MessageEvent by vms_reply_vi short-circuit patch. */
export function parseVmsChartFromMessageText(
  text: string,
): VmsChartPayload | null {
  if (!text || !text.includes("CREANOVA_VMS_CHART")) return null;
  const matches = [...text.matchAll(CHART_MARK_RE)];
  for (let i = matches.length - 1; i >= 0; i -= 1) {
    const raw = matches[i]?.[1]?.trim();
    if (!raw) continue;
    for (const candidate of [
      raw,
      raw.replace(/\\"/g, '"').replace(/\\\\/g, "\\"),
    ]) {
      try {
        const parsed = JSON.parse(candidate) as unknown;
        if (isVmsChartPayload(parsed)) return parsed;
      } catch {
        // try next decode
      }
    }
  }
  return null;
}
