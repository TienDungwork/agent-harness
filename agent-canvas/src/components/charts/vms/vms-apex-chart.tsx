import { useEffect, useId, useRef } from "react";
import ApexCharts from "apexcharts";
import type { ApexOptions } from "apexcharts";
import type { VmsChartPayload } from "./types";

/** Hex only — Apex SVG ignores most CSS variables. */
const FG = "#EEF2F7";
const MUTED = "#A3B0C4";
const GRID = "rgba(163,176,196,0.22)";
const PRIMARY = "#C9B974";
const SECONDARY = "#6EA8FE";
const PALETTE = [
  PRIMARY,
  SECONDARY,
  "#A5E75E",
  "#E76A5E",
  "#C084FC",
  "#38BDF8",
];

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

/** MM-DD / YYYY-MM-DD → D/M for a dense x-axis. */
function axisLabel(raw: string): string {
  const s = String(raw || "").trim();
  const m = s.match(/^(?:(\d{4})-)?(\d{2})-(\d{2})$/);
  if (m) return `${Number(m[3])}/${Number(m[2])}`;
  return labelVi(s);
}

function fmtN(n: number): string {
  return new Intl.NumberFormat("vi-VN").format(Math.round(n || 0));
}

function fmtAxis(v: number): string {
  const n = Math.abs(v);
  if (n >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `${Math.round(v / 1000)}k`;
  if (n >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return `${Math.round(v)}`;
}

function ChartShell({
  chart,
  children,
}: {
  chart: VmsChartPayload;
  children: React.ReactNode;
}) {
  return (
    <div
      className="my-2 w-full max-w-2xl overflow-hidden rounded-xl border border-[var(--oh-border-subtle)] bg-[var(--oh-surface-raised)]"
      data-testid="vms-analytics-chart"
      data-chart-engine="apex"
    >
      <div className="border-b border-[var(--oh-border-subtle)] px-4 pb-2 pt-3">
        <div className="text-sm font-semibold text-[var(--oh-foreground)]">
          {chart.title}
        </div>
        {chart.description ? (
          <div className="mt-0.5 text-xs text-[var(--oh-muted)]">
            {chart.description}
          </div>
        ) : null}
      </div>
      <div className="px-2 pb-1 pt-2">{children}</div>
      {chart.footer ? (
        <div className="px-4 pb-3 text-xs text-[var(--oh-muted)]">
          {chart.footer}
        </div>
      ) : null}
    </div>
  );
}

function baseChart(): NonNullable<ApexOptions["chart"]> {
  return {
    background: "transparent",
    foreColor: MUTED,
    toolbar: { show: false },
    zoom: { enabled: false },
    fontFamily: "inherit",
    animations: { enabled: true, speed: 400 },
    parentHeightOffset: 0,
    redrawOnParentResize: true,
    redrawOnWindowResize: true,
  };
}

function buildOptions(chart: VmsChartPayload): {
  type: "area" | "bar" | "donut";
  series: ApexOptions["series"];
  options: ApexOptions;
  height: number;
} {
  if (chart.type === "pie") {
    const labels = chart.data.map((d) => labelVi(d.label));
    const values = chart.data.map((d) => d.value || 0);
    const total = values.reduce((a, b) => a + b, 0);
    return {
      type: "donut",
      height: 320,
      series: values,
      options: {
        chart: { ...baseChart(), type: "donut", height: 320 },
        colors: PALETTE,
        labels,
        plotOptions: {
          pie: {
            donut: {
              size: "72%",
              labels: {
                show: true,
                name: { show: true, fontSize: "12px", color: MUTED, offsetY: 18 },
                value: {
                  show: true,
                  fontSize: "20px",
                  fontWeight: 700,
                  color: FG,
                  offsetY: -8,
                  formatter: (v) => fmtN(Number(v)),
                },
                total: {
                  show: true,
                  label: "Tổng",
                  fontSize: "12px",
                  color: MUTED,
                  formatter: () => fmtN(total),
                },
              },
            },
          },
        },
        dataLabels: { enabled: false },
        stroke: { width: 2, colors: ["#2C313F"] },
        legend: {
          position: "bottom",
          fontSize: "12px",
          labels: { colors: MUTED },
          formatter: (name, opts) => {
            const v = values[opts.seriesIndex] || 0;
            const pct = total ? Math.round((v / total) * 100) : 0;
            return `${name} · ${fmtN(v)} (${pct}%)`;
          },
        },
        tooltip: {
          theme: "dark",
          y: { formatter: (v: number) => fmtN(v ?? 0) },
        },
      },
    };
  }

  if (chart.type === "line" || chart.type === "area") {
    const categories = chart.data.map((d) => axisLabel(d.label));
    const dense = categories.length > 12;
    const series = [
      {
        name: chart.series?.value || "Lượt biển",
        data: chart.data.map((d) => d.value || 0),
      },
    ];
    if (chart.data.some((d) => d.value2 != null)) {
      series.push({
        name: chart.series?.value2 || "Series 2",
        data: chart.data.map((d) => d.value2 || 0),
      });
    }
    return {
      type: "area",
      height: 300,
      series,
      options: {
        chart: { ...baseChart(), type: "area", height: 300 },
        colors: PALETTE,
        stroke: { curve: "smooth", width: 2.5 },
        fill: {
          type: "gradient",
          gradient: {
            shadeIntensity: 0.35,
            opacityFrom: 0.4,
            opacityTo: 0.05,
            stops: [0, 90, 100],
          },
        },
        markers: {
          size: dense ? 0 : 3,
          hover: { size: 5 },
          strokeWidth: 0,
        },
        grid: {
          borderColor: GRID,
          strokeDashArray: 4,
          padding: { left: 8, right: 12 },
        },
        dataLabels: { enabled: false },
        tooltip: {
          theme: "dark",
          y: { formatter: (v: number) => fmtN(v ?? 0) },
        },
        legend: {
          show: series.length > 1,
          position: "top",
          horizontalAlign: "left",
          labels: { colors: MUTED },
        },
        xaxis: {
          categories,
          tickAmount: dense ? Math.min(8, categories.length) : undefined,
          labels: {
            rotate: dense ? -40 : 0,
            hideOverlappingLabels: true,
            style: { colors: MUTED, fontSize: "11px" },
          },
          axisBorder: { show: false },
          axisTicks: { show: false },
          tooltip: { enabled: false },
        },
        yaxis: {
          labels: {
            style: { colors: MUTED, fontSize: "11px" },
            formatter: (v) => fmtAxis(v),
          },
        },
      },
    };
  }

  // mixed-bar / multiple-bar → column
  const categories = chart.data.map((d) => labelVi(d.label));
  const hasSecond = chart.data.some((d) => d.value2 != null);
  const distributed = !hasSecond && chart.type === "mixed-bar";
  const series = hasSecond
    ? [
        {
          name: chart.series?.value || "Vào",
          data: chart.data.map((d) => d.value || 0),
        },
        {
          name: chart.series?.value2 || "Ra",
          data: chart.data.map((d) => d.value2 || 0),
        },
      ]
    : [
        {
          name: chart.series?.value || "Số lượng",
          data: chart.data.map((d) => d.value || 0),
        },
      ];
  return {
    type: "bar",
    height: 300,
    series,
    options: {
      chart: { ...baseChart(), type: "bar", height: 300 },
      colors: hasSecond ? [PRIMARY, SECONDARY] : PALETTE,
      plotOptions: {
        bar: {
          borderRadius: 5,
          columnWidth: hasSecond ? "55%" : categories.length > 8 ? "55%" : "42%",
          distributed,
        },
      },
      dataLabels: {
        enabled: categories.length <= 6,
        formatter: (v) => fmtAxis(Number(v)),
        style: { fontSize: "10px", colors: [FG] },
      },
      grid: {
        borderColor: GRID,
        strokeDashArray: 4,
        padding: { left: 8, right: 8 },
      },
      tooltip: {
        theme: "dark",
        y: { formatter: (v: number) => fmtN(v ?? 0) },
      },
      legend: {
        show: hasSecond,
        position: "top",
        horizontalAlign: "left",
        labels: { colors: MUTED },
      },
      xaxis: {
        categories,
        labels: { style: { colors: MUTED, fontSize: "11px" } },
        axisBorder: { show: false },
        axisTicks: { show: false },
      },
      yaxis: {
        labels: {
          style: { colors: MUTED, fontSize: "11px" },
          formatter: (v) => fmtAxis(v),
        },
      },
    },
  };
}

function ApexHost({ chart }: { chart: VmsChartPayload }) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ApexCharts | null>(null);
  const reactId = useId();
  const chartKey = JSON.stringify(chart);

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return undefined;

    const built = buildOptions(chart);
    const opts: ApexOptions = {
      ...built.options,
      chart: {
        ...built.options.chart,
        type: built.type,
        height: built.height,
        id: `vms-${reactId.replace(/:/g, "")}`,
      },
      series: built.series,
    };

    let cancelled = false;
    const run = async () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
      el.innerHTML = "";
      const instance = new ApexCharts(el, opts);
      chartRef.current = instance;
      await instance.render();
      if (cancelled) {
        instance.destroy();
        chartRef.current = null;
      }
    };
    void run();

    return () => {
      cancelled = true;
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
    // chartKey captures payload; chart object identity is unstable across renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartKey, reactId]);

  return <div ref={hostRef} className="w-full min-h-[280px]" />;
}

/** ApexCharts core (npm local — no CDN, no react-apexcharts wrapper). */
export function VmsApexChart({ chart }: { chart: VmsChartPayload }) {
  return (
    <ChartShell chart={chart}>
      <ApexHost chart={chart} />
    </ChartShell>
  );
}
