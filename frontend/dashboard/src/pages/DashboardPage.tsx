import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { listSamples } from "../services/api";
import type { SampleMetadata } from "../types/sample";

function DashboardPage(): JSX.Element {
  const [samples, setSamples] = useState<SampleMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSamples({ limit: 500 })
      .then(setSamples)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => {
    const labelCounts = new Map<string, number>();
    let visionOnly = 0;
    let sensorOnly = 0;
    let dual = 0;
    for (const s of samples) {
      const key = s.label ?? "未标注";
      labelCounts.set(key, (labelCounts.get(key) ?? 0) + 1);
      if (s.has_vision && s.has_sensor) dual += 1;
      else if (s.has_vision) visionOnly += 1;
      else if (s.has_sensor) sensorOnly += 1;
    }
    const totalWindows = samples.reduce((sum, s) => sum + s.window_count, 0);
    return { labelCounts, visionOnly, sensorOnly, dual, totalWindows };
  }, [samples]);

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>双模态监测系统 — 概览</h1>
      <p style={{ color: "#64748b" }}>
        三轴振动传感器 + 全局相机数据采集。本仪表盘负责样本入库、查询与频谱特征展示。
      </p>

      {error && <div style={errorBox}>加载失败: {error}</div>}

      <div style={cardGrid}>
        <StatCard label="总样本数" value={loading ? "..." : String(samples.length)} accent="#2563eb" />
        <StatCard label="窗口总数" value={loading ? "..." : String(stats.totalWindows)} accent="#0891b2" />
        <StatCard label="双模态样本" value={loading ? "..." : String(stats.dual)} accent="#16a34a" />
        <StatCard label="仅视觉 / 仅传感器" value={loading ? "..." : `${stats.visionOnly} / ${stats.sensorOnly}`} accent="#ca8a04" />
      </div>

      <section style={{ marginTop: 24 }}>
        <h2>按标签分布</h2>
        {stats.labelCounts.size === 0 ? (
          <div style={emptyStyle}>暂无数据。<Link to="/samples">前往样本页</Link>上传第一个特征文件。</div>
        ) : (
          <div style={cardGrid}>
            {[...stats.labelCounts.entries()].map(([label, count]) => (
              <StatCard key={label} label={label} value={String(count)} accent="#475569" />
            ))}
          </div>
        )}
      </section>

      <section style={{ marginTop: 24 }}>
        <h2>最近上传</h2>
        {samples.length === 0 ? (
          <div style={emptyStyle}>无上传记录</div>
        ) : (
          <ul style={listStyle}>
            {samples.slice(0, 5).map((s) => (
              <li key={s.sample_id} style={listItem}>
                <Link to={`/samples/${s.sample_id}`} style={{ color: "#2563eb", textDecoration: "none" }}>
                  <code>{s.sample_id}</code>
                </Link>
                <span style={{ color: "#64748b", marginLeft: 12 }}>
                  {s.label ?? "未标注"} · {s.window_count} 窗口 · {new Date(s.ingested_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string; accent: string }): JSX.Element {
  return (
    <div style={{
      background: "#fff",
      padding: 16,
      borderRadius: 8,
      borderLeft: `4px solid ${accent}`,
      boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
    }}>
      <div style={{ color: "#64748b", fontSize: 13 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 600, marginTop: 4 }}>{value}</div>
    </div>
  );
}

const cardGrid: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: 12,
  marginTop: 16
};

const listStyle: React.CSSProperties = {
  listStyle: "none",
  padding: 0,
  margin: 0,
  background: "#fff",
  borderRadius: 8,
  boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
};

const listItem: React.CSSProperties = {
  padding: "12px 16px",
  borderBottom: "1px solid #f1f5f9"
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
  marginTop: 16,
  padding: 24,
  background: "#fff",
  border: "1px dashed #cbd5e1",
  borderRadius: 8,
  color: "#64748b",
  textAlign: "center"
};

export default DashboardPage;
