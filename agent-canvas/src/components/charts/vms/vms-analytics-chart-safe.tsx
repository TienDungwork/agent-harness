import { Component, useEffect, useId, useState, type ReactNode } from "react";
import type { VmsChartPayload } from "./types";
import { VmsApexChart } from "./vms-apex-chart";
import { VmsCssBars } from "./vms-css-bars";

class ChartErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  componentDidCatch(error: Error) {
    console.error("[vms-chart] Apex render failed, using CSS fallback", error);
  }

  render() {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

/**
 * Prefer ApexCharts; if the SVG never mounts, fall back to CSS bars so the
 * user always sees a chart card.
 */
function ApexOrCss({ chart }: { chart: VmsChartPayload }) {
  const uid = useId().replace(/:/g, "");
  const [useCss, setUseCss] = useState(false);

  useEffect(() => {
    setUseCss(false);
    const timer = window.setTimeout(() => {
      const root = document.querySelector(`[data-vms-chart-id="${uid}"]`);
      const canvas = root?.querySelector(".apexcharts-canvas");
      if (!canvas) {
        console.warn("[vms-chart] Apex canvas missing — CSS fallback");
        setUseCss(true);
      }
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [chart, uid]);

  if (useCss) return <VmsCssBars chart={chart} />;
  return (
    <div data-vms-chart-id={uid} className="w-full">
      <VmsApexChart chart={chart} />
    </div>
  );
}

/** ApexCharts (local npm). CSS bars if Apex throws or never paints. */
export function VmsAnalyticsChartSafe({ chart }: { chart: VmsChartPayload }) {
  if (!chart?.data?.length) return null;
  return (
    <ChartErrorBoundary fallback={<VmsCssBars chart={chart} />}>
      <ApexOrCss chart={chart} />
    </ChartErrorBoundary>
  );
}
