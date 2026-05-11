import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import FeatureTimeSeriesChart from "../components/FeatureTimeSeriesChart";
import WindowFeatureTable from "../components/WindowFeatureTable";
import { deleteSample, getSample } from "../services/api";
import type { SampleDetail } from "../types/sample";

const DEFAULT_FIELDS = [
  "vision_dx_peak_hz",
  "vision_dy_peak_hz",
  "sensor_ax_peak_hz",
  "sensor_ay_peak_hz",
  "sensor_az_peak_hz"
];

function SampleDetailPage(): JSX.Element {
  const { sampleId } = useParams<{ sampleId: string }>();
  const navigate = useNavigate();

  const [detail, setDetail] = useState<SampleDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFields, setSelectedFields] = useState<string[]>([]);

  useEffect(() => {
    if (!sampleId) return;
    setLoading(true);
    getSample(sampleId)
      .then((data) => {
        setDetail(data);
        const available = data.rows.length > 0 ? Object.keys(data.rows[0]) : [];
        setSelectedFields(DEFAULT_FIELDS.filter((f) => available.includes(f)));
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [sampleId]);

  const numericFields = useMemo(() => {
    if (!detail || detail.rows.length === 0) return [];
    const sample = detail.rows[0];
    return Object.keys(sample).filter((k) => {
      const v = sample[k];
      return typeof v === "number" && k !== "center_time_s" && k !== "window_index";
    });
  }, [detail]);

  async function handleDelete(): Promise<void> {
    if (!sampleId) return;
    if (!window.confirm(`确认删除样本 ${sampleId}?同时会删除磁盘文件。`)) return;
    await deleteSample(sampleId);
    navigate("/samples");
  }

  if (loading) return <div>加载中...</div>;
  if (error) return <div style={errorBox}>加载失败: {error}</div>;
  if (!detail) return <div>未找到样本</div>;

  const meta = detail.metadata;

  return (
    <div>
      <Link to="/samples" style={{ color: "#2563eb", textDecoration: "none" }}>← 返回列表</Link>
      <div style={headerRow}>
        <h1 style={{ margin: "12px 0" }}><code>{meta.sample_id}</code></h1>
        <button onClick={handleDelete} style={btnDanger}>删除样本</button>
      </div>

      <div style={metaGrid}>
        <MetaItem label="标签" value={meta.label ?? "未标注"} />
        <MetaItem label="窗口数" value={String(meta.window_count)} />
        <MetaItem label="模态" value={[
          meta.has_vision && "vision",
          meta.has_sensor && "sensor"
        ].filter(Boolean).join(" + ") || "-"} />
        <MetaItem label="采集时间" value={meta.captured_at ? new Date(meta.captured_at).toLocaleString() : "-"} />
        <MetaItem label="入库时间" value={new Date(meta.ingested_at).toLocaleString()} />
        <MetaItem label="来源文件" value={meta.source_name ?? "-"} />
      </div>

      <section style={{ marginTop: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <h2 style={{ margin: "0 0 12px 0" }}>窗口特征时序</h2>
          <span style={{ color: "#64748b", fontSize: 13 }}>
            选中字段 {selectedFields.length} / {numericFields.length}
          </span>
        </div>
        <div style={fieldChips}>
          {numericFields.map((f) => {
            const active = selectedFields.includes(f);
            return (
              <button
                key={f}
                onClick={() => {
                  setSelectedFields(active
                    ? selectedFields.filter((x) => x !== f)
                    : [...selectedFields, f]);
                }}
                style={active ? chipActive : chipInactive}
              >
                {f}
              </button>
            );
          })}
        </div>
        <div style={{ background: "#fff", borderRadius: 8, padding: 16, marginTop: 12 }}>
          <FeatureTimeSeriesChart points={detail.rows} fields={selectedFields} />
        </div>
      </section>

      <section style={{ marginTop: 24 }}>
        <WindowFeatureTable rows={detail.rows} />
      </section>
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div style={metaItem}>
      <div style={{ color: "#64748b", fontSize: 12 }}>{label}</div>
      <div style={{ marginTop: 4, fontWeight: 500 }}>{value}</div>
    </div>
  );
}

const headerRow: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center"
};

const metaGrid: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: 12,
  marginTop: 16
};

const metaItem: React.CSSProperties = {
  background: "#fff",
  padding: 12,
  borderRadius: 8,
  boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
};

const fieldChips: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 6,
  padding: 12,
  background: "#fff",
  borderRadius: 8
};

const chipActive: React.CSSProperties = {
  background: "#2563eb",
  color: "#fff",
  border: "none",
  padding: "4px 10px",
  borderRadius: 16,
  cursor: "pointer",
  fontSize: 12
};

const chipInactive: React.CSSProperties = {
  background: "#f1f5f9",
  color: "#475569",
  border: "1px solid #e2e8f0",
  padding: "4px 10px",
  borderRadius: 16,
  cursor: "pointer",
  fontSize: 12
};

const btnDanger: React.CSSProperties = {
  background: "#dc2626",
  color: "#fff",
  border: "none",
  padding: "8px 16px",
  borderRadius: 6,
  cursor: "pointer"
};

const errorBox: React.CSSProperties = {
  padding: 12,
  background: "#fef2f2",
  border: "1px solid #fecaca",
  color: "#991b1b",
  borderRadius: 6
};

export default SampleDetailPage;
