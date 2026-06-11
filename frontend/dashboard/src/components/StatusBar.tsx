import type { DashboardOverview, WindowSample } from "../types/api";

interface Props {
  overview: DashboardOverview | null;
  lastRefreshAt: Date | null;
  apiBaseUrl: string;
  latestSample: WindowSample | null;
  backendDown?: boolean;
}

function StatusBar({ overview, lastRefreshAt, apiBaseUrl, latestSample, backendDown }: Props): JSX.Element {
  const offset = overview?.sync_offset_ms_p95 ?? null;
  const aligned = overview?.aligned_window_ratio ?? null;
  const analysisFps = readMetric(latestSample, "analysis_fps");
  const sensorHz = readMetric(latestSample, "sensor_sample_rate_hz");

  const offsetWarn = offset !== null && offset > 2.0;
  const alignedWarn = aligned !== null && aligned < 0.9;

  return (
    <div style={barStyle}>
      {backendDown && <span style={errStyle}>服务不可用</span>}
      <Item label="后端" value={compactApiBaseUrl(apiBaseUrl)} />
      <Divider />
      <Item label="任务" value={overview?.latest_task_id?.slice(-8) ?? "—"} />
      <Divider />
      <Item label="最新窗" value={overview?.latest_window_index != null ? `#${overview.latest_window_index}` : "—"} />
      <Divider />
      <Item label="视觉 FPS" value={analysisFps !== null ? analysisFps.toFixed(1) : "—"} />
      <Divider />
      <Item label="IMU Hz" value={sensorHz !== null ? sensorHz.toFixed(1) : "—"} />
      <Divider />
      <Item label="同步偏移 p95" value={offset !== null ? `${offset.toFixed(2)} ms` : "—"} warn={offsetWarn} />
      <Divider />
      <Item label="对齐率" value={aligned !== null ? `${(aligned * 100).toFixed(0)}%` : "—"} warn={alignedWarn} />
      <Divider />
      <Item
        label="漂移"
        value={overview?.sync_drift_ppm != null ? `${overview.sync_drift_ppm.toFixed(1)} ppm` : "—"}
      />
      <Divider />
      <Item
        label="窗口数"
        value={overview ? String(overview.effective_window_count) : "—"}
      />
      <span style={{ marginLeft: "auto", color: "#94a3b8", fontSize: 12 }}>
        {lastRefreshAt ? `刷新于 ${lastRefreshAt.toLocaleTimeString()}` : "—"}
      </span>
    </div>
  );
}

function readMetric(sample: WindowSample | null, key: string): number | null {
  if (!sample) return null;
  const value = sample[key];
  return typeof value === "number" && !Number.isNaN(value) ? value : null;
}

function compactApiBaseUrl(value: string): string {
  return value.replace(/^https?:\/\//, "");
}

function Item({ label, value, warn }: { label: string; value: string; warn?: boolean }): JSX.Element {
  return (
    <span style={{ color: warn ? "#f97316" : "#475569" }}>
      <span style={{ color: "#64748b", fontSize: 12, marginRight: 4 }}>{label}:</span>
      <span style={{ fontWeight: 600, fontSize: 13 }}>{value}</span>
    </span>
  );
}

function Divider(): JSX.Element {
  return <span style={{ width: 1, height: 14, background: "#cbd5e1" }} />;
}

const barStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 14,
  padding: "8px 16px",
  background: "#ffffff",
  border: "1px solid #e8e8e8",
  borderRadius: 8,
  fontSize: 13,
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)"
};

const errStyle: React.CSSProperties = {
  background: "#fef2f2",
  color: "#991b1b",
  padding: "2px 8px",
  borderRadius: 4,
  fontSize: 12,
  fontWeight: 600
};

export default StatusBar;
