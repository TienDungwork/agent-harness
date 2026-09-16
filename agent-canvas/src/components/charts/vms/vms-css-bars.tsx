import type { VmsChartPayload } from "./types";

const VT_LABEL: Record<string, string> = {
  MOTORCYCLE: "Xe máy",
  CAR: "Ô tô",
  TRUCK: "Xe tải",
  BUS: "Xe khách",
  IN: "Vào",
  OUT: "Ra",
};

function labelVi(raw: string): string {
  return VT_LABEL[raw] || VT_LABEL[raw.toUpperCase()] || raw;
}

/**
 * CSS-only bars — always visible (no Recharts / ResponsiveContainer).
 * Used as the primary VMS chart so chat never depends on lazy chunk load.
 */
export function VmsCssBars({ chart }: { chart: VmsChartPayload }) {
  const hasSecond = chart.data.some((d) => d.value2 != null);
  const max = Math.max(
    1,
    ...chart.data.map((d) =>
      hasSecond
        ? Math.max(d.value || 0, d.value2 || 0)
        : Math.max(d.value || 0, 0),
    ),
  );
  const s1 = chart.series?.value || "Giá trị";
  const s2 = chart.series?.value2;

  return (
    <div
      className="my-2 w-full max-w-xl rounded-xl border border-[var(--oh-border-subtle)] bg-[var(--oh-surface-raised)] p-4 text-[var(--oh-foreground)]"
      data-testid="vms-analytics-chart"
    >
      <div className="text-sm font-semibold">{chart.title}</div>
      {chart.description ? (
        <div className="mt-0.5 text-xs text-[var(--oh-muted)]">
          {chart.description}
        </div>
      ) : null}

      {hasSecond ? (
        <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-[var(--oh-muted)]">
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ background: "var(--chart-1)" }}
            />
            {s1}
          </span>
          {s2 ? (
            <span className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: "var(--chart-2)" }}
              />
              {s2}
            </span>
          ) : null}
        </div>
      ) : null}

      <ul className="mt-3 flex flex-col gap-2.5">
        {chart.data.map((row) => {
          const name = labelVi(row.label);
          const v1 = row.value || 0;
          const v2 = row.value2 || 0;
          const w1 = `${Math.round((v1 / max) * 100)}%`;
          const w2 = `${Math.round((v2 / max) * 100)}%`;
          return (
            <li key={row.key || row.label} className="text-xs">
              <div className="mb-1 flex items-baseline justify-between gap-2">
                <span className="font-medium">{name}</span>
                <span className="tabular-nums text-[var(--oh-muted)]">
                  {hasSecond ? `${v1} / ${v2}` : v1}
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-[var(--oh-surface-deep)]">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: w1,
                      background: "var(--chart-1)",
                      minWidth: v1 > 0 ? 4 : 0,
                    }}
                  />
                </div>
                {hasSecond ? (
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-[var(--oh-surface-deep)]">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: w2,
                        background: "var(--chart-2)",
                        minWidth: v2 > 0 ? 4 : 0,
                      }}
                    />
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>

      {chart.footer ? (
        <div className="mt-3 text-xs text-[var(--oh-muted)]">{chart.footer}</div>
      ) : null}
    </div>
  );
}
