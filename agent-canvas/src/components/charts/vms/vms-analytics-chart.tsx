import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  Area,
  AreaChart,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "#/components/charts/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "#/components/charts/ui/chart";
import {
  buildMixedBarConfig,
  slugKey,
  withFillKeys,
  type VmsChartPayload,
} from "./types";

function MixedBarChart({ chart }: { chart: VmsChartPayload }) {
  const data = withFillKeys(chart.data);
  const config = buildMixedBarConfig(chart.data);
  return (
    <ChartContainer config={config} className="aspect-auto h-[220px] w-full">
      <BarChart
        accessibilityLayer
        data={data}
        layout="vertical"
        margin={{ left: 8, right: 8 }}
      >
        <YAxis
          dataKey="label"
          type="category"
          tickLine={false}
          tickMargin={8}
          axisLine={false}
          width={88}
        />
        <XAxis dataKey="value" type="number" hide />
        <ChartTooltip
          cursor={false}
          content={<ChartTooltipContent hideLabel />}
        />
        <Bar dataKey="value" radius={5} />
      </BarChart>
    </ChartContainer>
  );
}

function MultipleBarChart({ chart }: { chart: VmsChartPayload }) {
  const s1 = chart.series?.value || "Series A";
  const s2 = chart.series?.value2 || "Series B";
  const config: ChartConfig = {
    value: { label: s1, color: "var(--chart-1)" },
    value2: { label: s2, color: "var(--chart-2)" },
  };
  return (
    <ChartContainer config={config} className="aspect-auto h-[220px] w-full">
      <BarChart accessibilityLayer data={chart.data} margin={{ left: 4, right: 4 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="label"
          tickLine={false}
          tickMargin={8}
          axisLine={false}
        />
        <ChartTooltip
          cursor={false}
          content={<ChartTooltipContent indicator="dashed" />}
        />
        <Bar dataKey="value" fill="var(--color-value)" radius={4} />
        <Bar dataKey="value2" fill="var(--color-value2)" radius={4} />
      </BarChart>
    </ChartContainer>
  );
}

function AreaLinearChart({ chart }: { chart: VmsChartPayload }) {
  const config: ChartConfig = {
    value: { label: chart.series?.value || "Số lượng", color: "var(--chart-1)" },
  };
  return (
    <ChartContainer config={config} className="aspect-auto h-[220px] w-full">
      <AreaChart
        accessibilityLayer
        data={chart.data}
        margin={{ left: 8, right: 8 }}
      >
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
        />
        <ChartTooltip
          cursor={false}
          content={<ChartTooltipContent indicator="dot" hideLabel />}
        />
        <Area
          dataKey="value"
          type="linear"
          fill="var(--color-value)"
          fillOpacity={0.4}
          stroke="var(--color-value)"
        />
      </AreaChart>
    </ChartContainer>
  );
}

function LineDotsChart({ chart }: { chart: VmsChartPayload }) {
  const hasSecond = chart.data.some((d) => d.value2 != null);
  const config: ChartConfig = {
    value: {
      label: chart.series?.value || "Số lượng",
      color: "var(--chart-1)",
    },
    ...(hasSecond
      ? {
          value2: {
            label: chart.series?.value2 || "Series B",
            color: "var(--chart-2)",
          },
        }
      : {}),
  };
  return (
    <ChartContainer config={config} className="aspect-auto h-[220px] w-full">
      <LineChart
        accessibilityLayer
        data={chart.data}
        margin={{ left: 8, right: 8 }}
      >
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
        />
        <ChartTooltip
          cursor={false}
          content={<ChartTooltipContent hideLabel />}
        />
        <Line
          dataKey="value"
          type="natural"
          stroke="var(--color-value)"
          strokeWidth={2}
          dot={{ fill: "var(--color-value)" }}
          activeDot={{ r: 5 }}
        />
        {hasSecond && (
          <Line
            dataKey="value2"
            type="natural"
            stroke="var(--color-value2)"
            strokeWidth={2}
            dot={{ fill: "var(--color-value2)" }}
          />
        )}
      </LineChart>
    </ChartContainer>
  );
}

function PieLabelChart({ chart }: { chart: VmsChartPayload }) {
  const data = chart.data.map((row, i) => {
    const key = row.key || slugKey(row.label);
    return {
      ...row,
      category: key,
      fill: `var(--color-${key})`,
    };
  });
  const config = buildMixedBarConfig(chart.data);
  return (
    <ChartContainer
      config={config}
      className="mx-auto aspect-square max-h-[240px] w-full [&_.recharts-pie-label-text]:fill-[var(--oh-foreground)]"
    >
      <PieChart>
        <ChartTooltip content={<ChartTooltipContent hideLabel />} />
        <Pie data={data} dataKey="value" label nameKey="label" />
      </PieChart>
    </ChartContainer>
  );
}

export function VmsAnalyticsChart({ chart }: { chart: VmsChartPayload }) {
  if (!chart.data.length) return null;

  let body: ReactNode;
  switch (chart.type) {
    case "mixed-bar":
      body = <MixedBarChart chart={chart} />;
      break;
    case "multiple-bar":
      body = <MultipleBarChart chart={chart} />;
      break;
    case "area":
      body = <AreaLinearChart chart={chart} />;
      break;
    case "line":
      body = <LineDotsChart chart={chart} />;
      break;
    case "pie":
      body = <PieLabelChart chart={chart} />;
      break;
    default:
      return null;
  }

  return (
    <Card className="my-2 w-full max-w-xl" data-testid="vms-analytics-chart">
      <CardHeader>
        <CardTitle>{chart.title}</CardTitle>
        {chart.description ? (
          <CardDescription>{chart.description}</CardDescription>
        ) : null}
      </CardHeader>
      <CardContent>{body}</CardContent>
      {chart.footer ? (
        <CardFooter className="text-xs text-[var(--oh-muted)]">
          {chart.footer}
        </CardFooter>
      ) : null}
    </Card>
  );
}
