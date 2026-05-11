import { useState } from "react";
import axios from "axios";

import { createTask } from "../services/api";
import type { CreateTaskRequest } from "../types/api";

interface Props {
  onCreated: () => void;
  onClose: () => void;
}

function TaskCreateModal({ onCreated, onClose }: Props): JSX.Element {
  const [deviceId, setDeviceId] = useState("rig-01");
  const [windowSize, setWindowSize] = useState(0.5);
  const [windowHop, setWindowHop] = useState(0.25);
  const [roi, setRoi] = useState({ x: "", y: "", w: "", h: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(): Promise<void> {
    if (!deviceId.trim()) {
      setError("device_id 不能为空");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body: CreateTaskRequest = {
        device_id: deviceId.trim(),
        window_size_s: windowSize,
        window_hop_s: windowHop
      };
      const num = (s: string): number | undefined =>
        s === "" || Number.isNaN(Number(s)) ? undefined : Number(s);
      const x = num(roi.x), y = num(roi.y), w = num(roi.w), h = num(roi.h);
      if (x !== undefined) body.roi_x = x;
      if (y !== undefined) body.roi_y = y;
      if (w !== undefined) body.roi_w = w;
      if (h !== undefined) body.roi_h = h;

      await createTask(body);
      onCreated();
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        setError("已有任务在运行,请先停止当前任务");
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
        <h2 style={{ marginTop: 0 }}>新建采样任务</h2>

        <Field label="设备 ID *">
          <input value={deviceId} onChange={(e) => setDeviceId(e.target.value)} style={inputStyle} />
        </Field>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Field label="窗口长度 (s)">
            <input
              type="number"
              step={0.05}
              min={0.05}
              value={windowSize}
              onChange={(e) => setWindowSize(Number(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="窗口步长 (s)">
            <input
              type="number"
              step={0.05}
              min={0.01}
              value={windowHop}
              onChange={(e) => setWindowHop(Number(e.target.value))}
              style={inputStyle}
            />
          </Field>
        </div>

        <div style={{ marginTop: 8 }}>
          <div style={{ color: "#64748b", fontSize: 13, marginBottom: 6 }}>ROI(可选,留空用后端默认)</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8 }}>
            {(["x", "y", "w", "h"] as const).map((k) => (
              <input
                key={k}
                type="number"
                placeholder={k}
                value={roi[k]}
                onChange={(e) => setRoi({ ...roi, [k]: e.target.value })}
                style={inputStyle}
              />
            ))}
          </div>
        </div>

        {error && <div style={errorStyle}>{error}</div>}

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 18 }}>
          <button onClick={onClose} disabled={busy} style={btnSecondary}>取消</button>
          <button onClick={handleSubmit} disabled={busy} style={btnPrimary}>
            {busy ? "创建中..." : "创建"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }): JSX.Element {
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ color: "#64748b", fontSize: 13, marginBottom: 4 }}>{label}</div>
      {children}
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
  minWidth: 440,
  boxShadow: "0 20px 50px rgba(0,0,0,0.2)"
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  border: "1px solid #cbd5e1",
  borderRadius: 6,
  fontSize: 14,
  boxSizing: "border-box"
};

const errorStyle: React.CSSProperties = {
  marginTop: 12,
  padding: 10,
  background: "#fef2f2",
  border: "1px solid #fecaca",
  color: "#991b1b",
  borderRadius: 6,
  fontSize: 13
};

const btnPrimary: React.CSSProperties = {
  background: "#1677ff",
  color: "#fff",
  border: "none",
  padding: "8px 18px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 14
};

const btnSecondary: React.CSSProperties = {
  background: "#e2e8f0",
  color: "#0f172a",
  border: "none",
  padding: "8px 18px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 14
};

export default TaskCreateModal;
