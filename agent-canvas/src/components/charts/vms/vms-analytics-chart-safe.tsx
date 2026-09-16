import { Component, type ReactNode } from "react";
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

/** ApexCharts (local npm). CSS bars only if Apex throws at runtime. */
export function VmsAnalyticsChartSafe({ chart }: { chart: VmsChartPayload }) {
  if (!chart?.data?.length) return null;
  return (
    <ChartErrorBoundary fallback={<VmsCssBars chart={chart} />}>
      <VmsApexChart chart={chart} />
    </ChartErrorBoundary>
  );
}
