import { useState } from "react";
import axios from "axios";

import { uploadHistory } from "../services/api";
import type { HistoryMetadata, IngestErrorBody } from "../types/api";

interface Props {
  onUploaded: (meta: HistoryMetadata) => void;
  onClose: () => void;
}

function UploadDialog({ onUploaded, onClose }: Props): JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(): Promise<void> {
    if (!file) {
      setError("请选择一个 .csv 或 .parquet 文件");
      return;
    }
    setBusy(true);
    setError(null);
    setMissing([]);
    try {
      const meta = await uploadHistory(file);
      onUploaded(meta);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 422) {
        const body = err.response.data as IngestErrorBody;
        setError(body.detail.message);
        setMissing(body.detail.missing_columns ?? []);
      } else if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail ?? err.message);
      } else {
        setError(String(err));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={dialogStyle} onClick={(e) => e.stopPropagation()}>
        <h2 style={{ marginTop: 0 }}>上传特征文件</h2>
        <p style={{ color: "#64748b", marginTop: 0 }}>
          支持 .csv / .parquet,需包含必填字段:
          <code style={codeStyle}> sample_id, window_index, center_time_s</code>
        </p>
        <input
          type="file"
          accept=".csv,.parquet"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {error && (
          <div style={errorStyle}>
            <div>{error}</div>
            {missing.length > 0 && (
              <div style={{ marginTop: 6, fontSize: 13 }}>
                缺失列: <code>{missing.join(", ")}</code>
              </div>
            )}
          </div>
        )}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
          <button onClick={onClose} disabled={busy} style={btnSecondary}>
            取消
          </button>
          <button onClick={handleSubmit} disabled={busy || !file} style={btnPrimary}>
            {busy ? "上传中..." : "上传"}
          </button>
        </div>
      </div>
    </div>
  );
}

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(15,23,42,0.4)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 50
};

const dialogStyle: React.CSSProperties = {
  background: "#fff",
  borderRadius: 8,
  padding: 24,
  minWidth: 420,
  boxShadow: "0 20px 50px rgba(0,0,0,0.2)"
};

const codeStyle: React.CSSProperties = {
  background: "#f1f5f9",
  padding: "1px 4px",
  borderRadius: 3
};

const errorStyle: React.CSSProperties = {
  marginTop: 12,
  padding: 10,
  background: "#fef2f2",
  border: "1px solid #fecaca",
  color: "#991b1b",
  borderRadius: 6
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
  padding: "8px 16px",
  borderRadius: 6,
  cursor: "pointer"
};

export default UploadDialog;
