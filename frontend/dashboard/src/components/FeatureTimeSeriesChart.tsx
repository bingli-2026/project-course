import ReactECharts from "echarts-for-react";

import type { HistoryRow } from "../types/api";

interface Props {
  points: HistoryRow[];
  fields: string[];
  height?: number;
}

const COLORS = ["#2563eb", "#dc2626", "#16a34a", "#ca8a04", "#9333ea", "#0891b2"];

function FeatureTimeSeriesChart({ points, fields, height = 360 }: Props): JSX.Element {
  if (points.length === 0 || fields.length === 0) {
    return (
      <div style={emptyStyle}>没有可绘制的数据(请选择至少一个字段)</div>
    );
  }

  const xAxisData = points.map((p) => Number(p.center_time_s ?? 0));
  const series = fields.map((field, idx) => ({
    name: field,
    type: "line" as const,
    data: points.map((p) => {
      const value = p[field];
      return typeof value === "number" ? value : null;
    }),
    smooth: true,
    showSymbol: false,
    lineStyle: { width: 2, color: COLORS[idx % COLORS.length] },
    itemStyle: { color: COLORS[idx % COLORS.length] }
  }));

  const option = {
    tooltip: { trigger: "axis" as const },
    legend: { type: "scroll" as const, top: 0 },
    grid: { left: 60, right: 24, bottom: 48, top: 48 },
    xAxis: {
      type: "category" as const,
      name: "center_time_s (s)",
      data: xAxisData.map((v) => v.toFixed(3)),
      boundaryGap: false
    },
    yAxis: { type: "value" as const, name: "Hz / value" },
    dataZoom: [{ type: "inside" as const }, { type: "slider" as const, height: 20 }],
    series
  };

  return <ReactECharts option={option} style={{ height, width: "100%" }} />;
}

const emptyStyle: React.CSSProperties = {
  padding: 24,
  textAlign: "center",
  color: "#64748b",
  background: "#fff",
  border: "1px dashed #cbd5e1",
  borderRadius: 8
};

export default FeatureTimeSeriesChart;
