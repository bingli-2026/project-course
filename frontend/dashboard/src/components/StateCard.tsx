import type { DashboardOverview } from "../types/api";

interface Props {
  overview: DashboardOverview | null;
  recentStates: { window_index: number; predicted_state: string | null; confidence: number | null }[];
}

const STATE_COLORS: Record<string, string> = {
  normal: "#16a34a",
  unbalance: "#ef4444",
  loose: "#f97316",
  misaligned: "#dc2626",
  unknown: "#94a3b8"
};

function StateCard({ overview, recentStates }: Props): JSX.Element {
  const state = overview?.latest_predicted_state ?? null;
  const latest = recentStates.length > 0 ? recentStates[recentStates.length - 1] : null;
  const conf = latest?.confidence ?? null;
  const color = state ? STATE_COLORS[state] ?? "#475569" : "#94a3b8";

  return (
    <div style={panelStyle}>
      <div style={headerLabel}>当前状态</div>
      <div
        style={{
          ...stateBoxStyle,
          background: `${color}1a`,
          borderColor: color,
          color
        }}
      >
        <div style={{ fontSize: 30, fontWeight: 700, letterSpacing: 1 }}>
          {state ? translateState(state) : "—"}
        </div>
        <div style={{ marginTop: 6, fontSize: 14, opacity: 0.85 }}>
          置信 {conf !== null ? conf.toFixed(2) : "—"}
        </div>
      </div>

      <Row label="模型版本" value={overview?.active_model_version ?? "—"} />
      <Row label="24h 成功率" value={overview ? `${(overview.task_success_rate_24h * 100).toFixed(0)}%` : "—"} />

      <div style={{ marginTop: 16 }}>
        <div style={historyHeader}>最近窗口</div>
        {recentStates.length === 0 ? (
          <div style={emptyRow}>无历史</div>
        ) : (
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>#</th>
                <th style={thStyle}>状态</th>
                <th style={thStyle}>置信</th>
              </tr>
            </thead>
            <tbody>
              {recentStates.slice(-10).reverse().map((r) => {
                const c = r.predicted_state ? STATE_COLORS[r.predicted_state] ?? "#475569" : "#94a3b8";
                return (
                  <tr key={r.window_index}>
                    <td style={tdMonoStyle}>{r.window_index}</td>
                    <td style={{ ...tdStyle, color: c, fontWeight: 600 }}>
                      {r.predicted_state ? translateState(r.predicted_state) : "—"}
                    </td>
                    <td style={tdMonoStyle}>{r.confidence !== null ? r.confidence.toFixed(2) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function translateState(s: string): string {
  const map: Record<string, string> = {
    normal: "正常",
    unbalance: "不平衡",
    loose: "松动",
    misaligned: "不对中",
    unknown: "未知"
  };
  return map[s] ?? s;
}

function Row({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid #f1f5f9" }}>
      <span style={{ color: "#64748b", fontSize: 13 }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 500 }}>{value}</span>
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #e8e8e8",
  borderRadius: 8,
  padding: 16,
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  height: "100%"
};

const headerLabel: React.CSSProperties = { color: "#64748b", fontSize: 13, marginBottom: 8 };

const stateBoxStyle: React.CSSProperties = {
  border: "2px solid",
  borderRadius: 8,
  padding: 16,
  textAlign: "center",
  marginBottom: 16
};

const historyHeader: React.CSSProperties = {
  color: "#475569",
  fontSize: 13,
  fontWeight: 600,
  marginBottom: 6
};

const emptyRow: React.CSSProperties = {
  padding: 10,
  textAlign: "center",
  color: "#94a3b8",
  fontSize: 13
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 12
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "4px 6px",
  background: "#f8fafc",
  fontSize: 11,
  color: "#64748b",
  fontWeight: 600
};

const tdStyle: React.CSSProperties = { padding: "4px 6px", borderBottom: "1px solid #f1f5f9" };
const tdMonoStyle: React.CSSProperties = {
  ...tdStyle,
  fontVariantNumeric: "tabular-nums",
  color: "#475569"
};

export default StateCard;
