import { useState } from "react";

import { stopTask } from "../services/api";
import type { DashboardOverview, TaskStatus } from "../types/api";
import TaskCreateModal from "./TaskCreateModal";

interface Props {
  overview: DashboardOverview | null;
  windowCount: number;
  onTaskCreated: () => void;
  onTaskStopped: () => void;
}

const STATUS_META: Record<TaskStatus, { label: string; color: string; pulse: boolean }> = {
  pending: { label: "等待中", color: "#94a3b8", pulse: false },
  running: { label: "运行中", color: "#22c55e", pulse: true },
  succeeded: { label: "已完成", color: "#16a34a", pulse: false },
  failed: { label: "失败", color: "#ef4444", pulse: false }
};

function TaskBar({ overview, windowCount, onTaskCreated, onTaskStopped }: Props): JSX.Element {
  const [showCreate, setShowCreate] = useState(false);
  const [stopping, setStopping] = useState(false);

  const status = overview?.latest_status ?? null;
  const meta = status ? STATUS_META[status] : null;
  const running = status === "running";

  async function handleStop(): Promise<void> {
    if (!overview?.latest_task_id) return;
    setStopping(true);
    try {
      await stopTask(overview.latest_task_id);
      onTaskStopped();
    } finally {
      setStopping(false);
    }
  }

  return (
    <div style={barStyle}>
      <div style={leftGroup}>
        <span
          style={{
            ...statusDot,
            background: meta?.color ?? "#cbd5e1",
            boxShadow: meta?.pulse ? `0 0 0 4px ${meta.color}33` : "none",
            animation: meta?.pulse ? "pulse 1.4s ease-in-out infinite" : undefined
          }}
        />
        <span style={statusLabel}>{meta?.label ?? "无任务"}</span>
        <Divider />
        <span style={metaText}>
          {overview?.latest_task_id ? (
            <>任务 <code style={codeStyle}>{overview.latest_task_id.slice(-8)}</code></>
          ) : "—"}
        </span>
        <Divider />
        <span style={metaText}>
          窗口 {windowCount} / {overview?.effective_window_count ?? 0}
        </span>
      </div>
      <div style={rightGroup}>
        <button
          onClick={() => setShowCreate(true)}
          style={btnPrimary}
          title={running ? "创建会自动停止当前任务" : undefined}
        >
          + 新建任务
        </button>
        <button onClick={handleStop} disabled={!running || stopping} style={running ? btnDanger : btnDisabled}>
          {stopping ? "停止中..." : "停止"}
        </button>
      </div>

      {showCreate && (
        <TaskCreateModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            onTaskCreated();
          }}
        />
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 4px rgba(34,197,94,0.2); }
          50%      { box-shadow: 0 0 0 9px rgba(34,197,94,0.05); }
        }
      `}</style>
    </div>
  );
}

function Divider(): JSX.Element {
  return <span style={{ width: 1, height: 20, background: "#cbd5e1" }} />;
}

const barStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  background: "#ffffff",
  border: "1px solid #e8e8e8",
  borderRadius: 8,
  padding: "12px 16px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)"
};

const leftGroup: React.CSSProperties = { display: "flex", alignItems: "center", gap: 14 };
const rightGroup: React.CSSProperties = { display: "flex", gap: 8 };

const statusDot: React.CSSProperties = {
  display: "inline-block",
  width: 12,
  height: 12,
  borderRadius: "50%"
};

const statusLabel: React.CSSProperties = { fontWeight: 600, color: "#0f172a" };
const metaText: React.CSSProperties = { color: "#475569", fontSize: 14 };
const codeStyle: React.CSSProperties = {
  background: "#f1f5f9",
  padding: "2px 6px",
  borderRadius: 4,
  fontSize: 13
};

const btnBase: React.CSSProperties = {
  border: "none",
  padding: "8px 16px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 14,
  fontWeight: 500
};
const btnPrimary: React.CSSProperties = { ...btnBase, background: "#1677ff", color: "#fff" };
const btnDanger: React.CSSProperties = { ...btnBase, background: "#ef4444", color: "#fff" };
const btnDisabled: React.CSSProperties = {
  ...btnBase,
  background: "#e2e8f0",
  color: "#94a3b8",
  cursor: "not-allowed"
};

export default TaskBar;
