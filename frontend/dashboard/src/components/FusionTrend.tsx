import { useMemo } from "react";
import ReactECharts from "echarts-for-react";

import type { WindowSample } from "../types/api";

interface Props {
  windows: WindowSample[];
}

function FusionTrend({ windows }: Props): JSX.Element {
  const option = useMemo(() => buildOption(windows), [windows]);
  const isEmpty = windows.length === 0;

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>
        <h3 style={{ margin: 0, fontSize: 15 }}>融合频率趋势</h3>
        <span style={metaStyle}>共 {windows.length} 窗</span>
      </div>
      {isEmpty ? (
        <div style={emptyStyle}>等待第一个窗口...</div>
      ) : (
        <ReactECharts option={option} style={{ height: 320, width: "100%" }} notMerge />
      )}
    </div>
  );
}

function buildOption(windows: WindowSample[]): Record<string, unknown> {
  const indexAxis = windows.map((w) => w.window_index);
  const fused = windows.map((w) => num(w.fused_dominant_freq_hz));
  const conf = windows.map((w) => num(w.fusion_confidence));

  // Mark areas where confidence drops below 0.5
  const markAreas: Array<Array<{ xAxis: number }>> = [];
  let start: number | null = null;
  windows.forEach((w, i) => {
    const c = num(w.fusion_confidence);
    if (c !== null && c < 0.5 && start === null) start = i;
    if ((c === null || c >= 0.5) && start !== null) {
      markAreas.push([{ xAxis: windows[start].window_index }, { xAxis: w.window_index }]);
      start = null;
    }
  });
  if (start !== null) {
    markAreas.push([
      { xAxis: windows[start].window_index },
      { xAxis: windows[windows.length - 1].window_index }
    ]);
  }

  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: ["融合主频", "置信度"] },
    grid: { left: 60, right: 60, bottom: 36, top: 32 },
    xAxis: { type: "category", data: indexAxis, name: "window" },
    yAxis: [
      { type: "value", name: "Hz", position: "left" },
      { type: "value", name: "confidence", position: "right", min: 0, max: 1 }
    ],
    series: [
      {
        name: "融合主频",
        type: "line",
        data: fused,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 3, color: "#1677ff" },
        markArea: markAreas.length
          ? {
              itemStyle: { color: "rgba(148, 163, 184, 0.18)" },
              data: markAreas
            }
          : undefined
      },
      {
        name: "置信度",
        type: "line",
        yAxisIndex: 1,
        data: conf,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: "#94a3b8", type: "dashed" }
      }
    ]
  };
}

function num(v: unknown): number | null {
  return typeof v === "number" && !Number.isNaN(v) ? v : null;
}

const panelStyle: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #e8e8e8",
  borderRadius: 8,
  padding: 14,
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  height: "100%"
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: 8
};

const metaStyle: React.CSSProperties = { color: "#64748b", fontSize: 13 };

const emptyStyle: React.CSSProperties = {
  padding: 36,
  textAlign: "center",
  color: "#94a3b8",
  background: "#f8fafc",
  borderRadius: 6
};

export default FusionTrend;
