import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import UploadDialog from "../components/UploadDialog";
import { listSamples } from "../services/api";
import type { SampleMetadata } from "../types/sample";

function SamplesListPage(): JSX.Element {
  const navigate = useNavigate();
  const [samples, setSamples] = useState<SampleMetadata[]>([]);
  const [labelFilter, setLabelFilter] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listSamples(labelFilter ? { label: labelFilter } : {});
      setSamples(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [labelFilter]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const labels = Array.from(
    new Set(samples.map((s) => s.label).filter((l): l is string => Boolean(l)))
  );

  return (
    <div>
      <div style={headerRow}>
        <h1 style={{ margin: 0 }}>样本列表</h1>
        <button onClick={() => setShowUpload(true)} style={btnPrimary}>
          + 上传特征文件
        </button>
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 16 }}>
        <label style={{ color: "#475569" }}>按标签筛选:</label>
        <select
          value={labelFilter}
          onChange={(e) => setLabelFilter(e.target.value)}
          style={selectStyle}
        >
          <option value="">全部</option>
          {labels.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
        <button onClick={refresh} style={btnSecondary}>刷新</button>
      </div>

      {error && <div style={errorBox}>加载失败: {error}</div>}
      {loading && <div style={{ marginTop: 16 }}>加载中...</div>}

      {!loading && samples.length === 0 && (
        <div style={emptyStyle}>
          还没有样本。点击右上角"上传"或把 CSV/Parquet 文件放进 <code>data/samples/</code> 后重启后端。
        </div>
      )}

      {samples.length > 0 && (
        <table style={tableStyle}>
          <thead>
            <tr style={trHeader}>
              <th style={thStyle}>Sample ID</th>
              <th style={thStyle}>标签</th>
              <th style={thStyle}>模态</th>
              <th style={thStyle}>窗口数</th>
              <th style={thStyle}>采集时间</th>
              <th style={thStyle}>来源</th>
            </tr>
          </thead>
          <tbody>
            {samples.map((s) => (
              <tr
                key={s.sample_id}
                onClick={() => navigate(`/samples/${s.sample_id}`)}
                style={trBody}
              >
                <td style={tdStyle}><code>{s.sample_id}</code></td>
                <td style={tdStyle}>{s.label ?? <em style={{ color: "#94a3b8" }}>未标注</em>}</td>
                <td style={tdStyle}>
                  {s.has_vision && <Badge color="#0369a1">vision</Badge>}
                  {s.has_sensor && <Badge color="#15803d">sensor</Badge>}
                </td>
                <td style={tdStyle}>{s.window_count}</td>
                <td style={tdStyle}>{s.captured_at ? new Date(s.captured_at).toLocaleString() : "-"}</td>
                <td style={tdStyle}>{s.source_name ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showUpload && (
        <UploadDialog
          onClose={() => setShowUpload(false)}
          onUploaded={(meta) => {
            setShowUpload(false);
            navigate(`/samples/${meta.sample_id}`);
          }}
        />
      )}
    </div>
  );
}

function Badge({ color, children }: { color: string; children: React.ReactNode }): JSX.Element {
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 8px",
      marginRight: 4,
      borderRadius: 4,
      background: `${color}22`,
      color,
      fontSize: 12,
      fontWeight: 500
    }}>{children}</span>
  );
}

const headerRow: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center"
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  marginTop: 16,
  background: "#fff",
  borderRadius: 8,
  overflow: "hidden",
  boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
};

const trHeader: React.CSSProperties = {
  background: "#f8fafc",
  borderBottom: "1px solid #e2e8f0"
};

const trBody: React.CSSProperties = {
  borderBottom: "1px solid #f1f5f9",
  cursor: "pointer"
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 14px",
  fontSize: 13,
  color: "#475569",
  fontWeight: 600
};

const tdStyle: React.CSSProperties = {
  padding: "10px 14px",
  fontSize: 14
};

const selectStyle: React.CSSProperties = {
  padding: "6px 10px",
  border: "1px solid #cbd5e1",
  borderRadius: 6,
  background: "#fff"
};

const btnPrimary: React.CSSProperties = {
  background: "#2563eb",
  color: "#fff",
  border: "none",
  padding: "8px 16px",
  borderRadius: 6,
  cursor: "pointer"
};

const btnSecondary: React.CSSProperties = {
  background: "#e2e8f0",
  color: "#0f172a",
  border: "none",
  padding: "6px 12px",
  borderRadius: 6,
  cursor: "pointer"
};

const errorBox: React.CSSProperties = {
  marginTop: 16,
  padding: 12,
  background: "#fef2f2",
  border: "1px solid #fecaca",
  color: "#991b1b",
  borderRadius: 6
};

const emptyStyle: React.CSSProperties = {
  marginTop: 24,
  padding: 24,
  background: "#fff",
  border: "1px dashed #cbd5e1",
  borderRadius: 8,
  color: "#64748b",
  textAlign: "center"
};

export default SamplesListPage;
