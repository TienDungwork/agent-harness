import { describe, expect, it } from "vitest";
import {
  isVmsAnalyticsToolName,
  parseVmsChartFromObservationText,
} from "#/components/charts/vms/parse-vms-chart";
import {
  parseVmsChartFromMessageText,
  stripVmsChartMarker,
} from "#/components/charts/vms/parse-vms-chart-marker";

describe("parseVmsChartFromObservationText", () => {
  it("parses chart from slim MCP JSON", () => {
    const text = JSON.stringify({
      ok: true,
      reply_vi: "Toyota: 5",
      chart: {
        type: "mixed-bar",
        title: "Theo hãng",
        data: [{ label: "TOYOTA", value: 5, key: "toyota" }],
      },
    });
    const chart = parseVmsChartFromObservationText(text);
    expect(chart?.type).toBe("mixed-bar");
    expect(chart?.data).toHaveLength(1);
  });

  it("parses chart after tool-executed prefix", () => {
    const json = JSON.stringify({
      ok: true,
      reply_vi: "hi",
      chart: {
        type: "multiple-bar",
        title: "Ra / vào",
        data: [{ label: "CAR", value: 1, value2: 2 }],
        series: { value: "Vào", value2: "Ra" },
      },
    });
    const text = `[Tool 'vms_query' executed.]\n${json}`;
    expect(parseVmsChartFromObservationText(text)?.type).toBe("multiple-bar");
  });

  it("returns null when chart missing", () => {
    expect(
      parseVmsChartFromObservationText(
        JSON.stringify({ ok: true, reply_vi: "hi" }),
      ),
    ).toBeNull();
  });
});

describe("parseVmsChartFromMessageText", () => {
  it("extracts and strips embedded chart marker", () => {
    const chart = {
      type: "multiple-bar" as const,
      title: "Ra / vào theo loại xe",
      data: [{ label: "MOTORCYCLE", value: 43, value2: 1054 }],
      series: { value: "Vào (IN)", value2: "Ra (OUT)" },
    };
    const text = `Ngày 08/09/2026: tổng 1872.\n\n<!--CREANOVA_VMS_CHART:${JSON.stringify(chart)}-->`;
    expect(parseVmsChartFromMessageText(text)?.title).toBe(
      "Ra / vào theo loại xe",
    );
    expect(stripVmsChartMarker(text)).toBe("Ngày 08/09/2026: tổng 1872.");
  });
});

describe("isVmsAnalyticsToolName", () => {
  it("matches vms tools", () => {
    expect(isVmsAnalyticsToolName("vms_query")).toBe(true);
    expect(isVmsAnalyticsToolName("creanova_infra__vms_query")).toBe(true);
    expect(isVmsAnalyticsToolName("terminal")).toBe(false);
  });
});
