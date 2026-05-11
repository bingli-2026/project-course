import { useMemo, useState } from "react";

import type { HistoryRow } from "../types/api";

interface Props {
  rows: HistoryRow[];
}

const PRIORITY_FIRST = [
  "window_index",
  "center_time_s",
  "label",
  "modality"
];

function WindowFeatureTable({ rows }: Props): JSX.Element {
  const [expanded, setExpanded] = useState(false);

  const columns = useMemo(() => {
    if (rows.length === 0) return [];
    const all = Object.keys(rows[0]);
    const ordered = [
      ...PRIORITY_FIRST.filter((c) => all.includes(c)),
      ...all.filter((c) => !PRIORITY_FIRST.includes(c))
    ];
    return ordered;
  }, [rows]);

  if (rows.length === 0) {
    return <div style={emptyStyle}>无窗口数据</div>;
  }

  const visible = expanded ? rows : rows.slice(0, 5);

  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: 16, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>窗口特征(共 {rows.length} 行)</h3>
        {rows.length > 5 && (
          <button onClick={() => setExpanded(!expanded)} style={btnSecondary}>
            {expanded ? "收起" : `展开剩余 ${rows.length - 5} 行`}
          </button>
        )}
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={tableStyle}>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c} style={thStyle}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, idx) => (
              <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9" }}>
                {columns.map((c) => (
                  <td key={c} style={tdStyle}>{formatCell(row[c])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4);
  }
  return String(value);
}

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 12
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "6px 10px",
  background: "#f8fafc",
  position: "sticky",
  top: 0,
  fontWeight: 600,
  color: "#475569",
  whiteSpace: "nowrap"
};

const tdStyle: React.CSSProperties = {
  padding: "6px 10px",
  whiteSpace: "nowrap",
  fontVariantNumeric: "tabular-nums"
};

const emptyStyle: React.CSSProperties = {
  padding: 16,
  color: "#64748b",
  background: "#fff",
  borderRadius: 8
};

const btnSecondary: React.CSSProperties = {
  background: "#e2e8f0",
  color: "#0f172a",
  border: "none",
  padding: "6px 12px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 12
};

export default WindowFeatureTable;
