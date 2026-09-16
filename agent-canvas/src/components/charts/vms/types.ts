import type { ChartConfig } from "#/components/charts/ui/chart";

/** Compact chart payload kept in MCP slim JSON (alongside reply_vi). */
export type VmsChartType =
  | "mixed-bar"
  | "multiple-bar"
  | "area"
  | "line"
  | "pie";

export interface VmsChartSeriesPoint {
  label: string;
  value: number;
  /** Extra series for multiple-bar / multi-line */
  value2?: number;
  fill?: string;
  key?: string;
}

export interface VmsChartPayload {
  type: VmsChartType;
  title: string;
  description?: string;
  footer?: string;
  data: VmsChartSeriesPoint[];
  /** Labels for series when type is multiple-bar / line */
  series?: { value: string; value2?: string };
}

export function isVmsChartPayload(value: unknown): value is VmsChartPayload {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.type === "string" &&
    typeof v.title === "string" &&
    Array.isArray(v.data)
  );
}

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

export function buildMixedBarConfig(data: VmsChartSeriesPoint[]): ChartConfig {
  const config: ChartConfig = {
    value: { label: "Số lượng" },
  };
  data.forEach((row, i) => {
    const key = row.key || slugKey(row.label);
    config[key] = {
      label: row.label,
      color: row.fill || CHART_COLORS[i % CHART_COLORS.length],
    };
  });
  return config;
}

export function slugKey(label: string): string {
  const s = label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
  return s || "other";
}

export function withFillKeys(
  data: VmsChartSeriesPoint[],
): Array<VmsChartSeriesPoint & { category: string }> {
  return data.map((row) => {
    const key = row.key || slugKey(row.label);
    return {
      ...row,
      category: key,
      key,
      fill: row.fill || `var(--color-${key})`,
    };
  });
}
