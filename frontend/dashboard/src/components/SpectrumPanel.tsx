import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";

import { getTaskSpectra } from "../services/api";
import type { AxisSpectrum, SpectrumAxis, WindowSpectraResponse } from "../types/api";

interface Props {
  taskId: string | null;
  windowIndex: number | null;
}

type TabKey = "accel" | "gyro" | "vision";

const TABS: { key: TabKey; label: string; axes: SpectrumAxis[]; colors: string[] }[] = [
  {
    key: "accel",
    label: "加速度计",
    axes: ["sensor_ax", "sensor_ay", "sensor_az"],
    colors: ["#1677ff", "#dc2626", "#16a34a"]
  },
  {
    key: "gyro",
    label: "陀螺仪",
    axes: ["sensor_gx", "sensor_gy", "sensor_gz"],
    colors: ["#0891b2", "#ca8a04", "#9333ea"]
  },
  {
    key: "vision",
    label: "视觉",
    axes: ["vision_dx", "vision_dy"],
    colors: ["#2563eb", "#db2777"]
  }
];

function SpectrumPanel({ taskId, windowIndex }: Props): JSX.Element {
  const [tab, setTab] = useState<TabKey>("accel");
  const [spectra, setSpectra] = useState<WindowSpectraResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId || windowIndex === null || windowIndex === undefined) {
      setSpectra(null);
      return;
    }
    let cancelled = false;
    getTaskSpectra(taskId, windowIndex)
      .then((data) => {
        if (!cancelled) {
          setSpectra(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [taskId, windowIndex]);

  const tabDef = TABS.find((t) => t.key === tab)!;
  const option = useMemo(() => buildOption(spectra, tabDef), [spectra, tabDef]);

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>
        <div style={{ display: "flex", gap: 4 }}>
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={t.key === tab ? tabActive : tabInactive}
            >
              {t.label}
            </button>
          ))}
        </div>
        <span style={metaStyle}>
          {windowIndex !== null && windowIndex !== undefined ? `窗口 #${windowIndex}` : "无窗口"}
        </span>
      </div>

      {error && <div style={errorStyle}>频谱加载失败: {error}</div>}

      {!spectra && !error && (
        <div style={emptyStyle}>暂无频谱数据(等待第一个窗口)</div>
      )}

      {spectra && (
        <ReactECharts option={option} style={{ height: 320, width: "100%" }} notMerge />
      )}
    </div>
  );
}

function buildOption(
  spectra: WindowSpectraResponse | null,
  tabDef: typeof TABS[number]
): Record<string, unknown> {
  if (!spectra) return {};

  const series = tabDef.axes
    .map((axis, idx) => {
      const data = spectra[axis] as AxisSpectrum | null;
      if (!data) return null;
      const peakIdx = data.power.indexOf(Math.max(...data.power));
      const peakHz = data.freq_hz[peakIdx];
      return {
        name: axis,
        type: "line" as const,
        data: data.freq_hz.map((f, i) => [f, data.power[i]]),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: tabDef.colors[idx] },
        itemStyle: { color: tabDef.colors[idx] },
        markLine: {
          symbol: "none",
          lineStyle: { color: tabDef.colors[idx], type: "dashed" as const, width: 1 },
          label: { formatter: `${peakHz.toFixed(1)} Hz`, fontSize: 11 },
          data: [{ xAxis: peakHz }]
        }
      };
    })
    .filter((s): s is NonNullable<typeof s> => s !== null);

  return {
    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
    legend: { top: 0 },
    grid: { left: 60, right: 24, bottom: 36, top: 32 },
    xAxis: { type: "value", name: "Hz", nameLocation: "end" },
    yAxis: { type: "value", name: "Power" },
    series
  };
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

const tabActive: React.CSSProperties = {
  background: "#1677ff",
  color: "#fff",
  border: "none",
  padding: "5px 12px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 13
};

const tabInactive: React.CSSProperties = {
  background: "#f1f5f9",
  color: "#475569",
  border: "1px solid #e2e8f0",
  padding: "5px 12px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 13
};

const metaStyle: React.CSSProperties = { color: "#64748b", fontSize: 13 };

const errorStyle: React.CSSProperties = {
  padding: 10,
  background: "#fef2f2",
  border: "1px solid #fecaca",
  color: "#991b1b",
  borderRadius: 6,
  fontSize: 13
};

const emptyStyle: React.CSSProperties = {
  padding: 36,
  textAlign: "center",
  color: "#94a3b8",
  background: "#f8fafc",
  borderRadius: 6
};

export default SpectrumPanel;
