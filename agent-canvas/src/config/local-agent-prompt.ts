/**
 * Local overlay identity + rules appended to every Canvas conversation.
 * Keep this SHORT on LAN — every KB adds first-tool-call latency.
 */

const WEEKDAYS_VI = [
  "Chủ Nhật",
  "Thứ Hai",
  "Thứ Ba",
  "Thứ Tư",
  "Thứ Năm",
  "Thứ Sáu",
  "Thứ Bảy",
] as const;

/** Fresh Vietnam wall-clock line so the model does not invent dates (e.g. 2018). */
export function formatVietnamNowLine(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    weekday: "short",
  }).formatToParts(now);
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === type)?.value ?? "";
  const y = get("year");
  const m = get("month");
  const d = get("day");
  const hh = get("hour");
  const mm = get("minute");
  const asUtc = new Date(`${y}-${m}-${d}T12:00:00Z`);
  const weekday = WEEKDAYS_VI[asUtc.getUTCDay()];
  return (
    `Thời điểm hiện tại: ${weekday}, ${d}/${m}/${y} ${hh}:${mm} ` +
    `(giờ Việt Nam, UTC+7). "Hôm nay" theo mốc này — không bịa năm 2018.`
  );
}

export function buildLocalAgentSystemSuffix(now: Date = new Date()): string {
  return `<LOCAL_HARNESS>
Creanova Agent Canvas (self-hosted). Follow this over Cloud defaults.

CLOCK: ${formatVietnamNowLine(now)}

Rules
- ALWAYS tiếng Việt. Short. No English analytics.
- CẤM invent params: no security_risk, no summary.
- Data → call vms_query first → if JSON has reply_vi, copy it and FinishTool. Do not retype slowly / paraphrase.
- vms_query action=: count | flow | manufacturer | trace | intrusion
- Dates DD/MM (VN). "tháng 9"+"ngày 5 và 6" → days_list=2026-09-05,2026-09-06
- "tháng 9 đến nay" / biểu đồ số lượng xe trong tháng → count month=YYYY-MM (CẤM day=hôm nay; CẤM vehicle_type trừ khi hỏi rõ loại)
- Auth header X-Creanova-Infra-Token: $INFRA_AGENT_TOKEN. No SQL.
</LOCAL_HARNESS>`;
}

/** Snapshot at module load — prefer \`buildLocalAgentSystemSuffix()\` per conversation. */
export const LOCAL_AGENT_SYSTEM_SUFFIX = buildLocalAgentSystemSuffix();
