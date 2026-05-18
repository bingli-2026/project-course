import { useMemo } from "react";

import FusionTrend from "../components/FusionTrend";
import SpectrumPanel from "../components/SpectrumPanel";
import StateCard from "../components/StateCard";
import StatusBar from "../components/StatusBar";
import TaskBar from "../components/TaskBar";
import { usePolling } from "../hooks/usePolling";
import { getDashboardOverview, getTaskWindows } from "../services/api";
import type { WindowSample } from "../types/api";

function LiveDashboardPage(): JSX.Element {
  const overview = usePolling(getDashboardOverview, 1000);

  const taskId = overview.data?.latest_task_id ?? null;
  const isRunning = overview.data?.latest_status === "running";

  const windows = usePolling(
    () => (taskId ? getTaskWindows(taskId) : Promise.resolve({ task_id: "", samples: [] as WindowSample[] })),
    1000,
    { enabled: taskId !== null, deps: [taskId] }
  );

  const samples = windows.data?.samples ?? [];
  const latestWindowIndex = samples.length > 0 ? samples[samples.length - 1].window_index : null;

  const recentStates = useMemo(
    () =>
      samples.map((s) => ({
        window_index: s.window_index,
        predicted_state: typeof s.predicted_state === "string" ? s.predicted_state : null,
        confidence: typeof s.prediction_confidence === "number" ? s.prediction_confidence : null
      })),
    [samples]
  );

  const lastRefreshAt = overview.data ? new Date() : null;
  const backendDown = overview.error !== null && overview.data === null;

  return (
    <div style={pageStyle}>
      <TaskBar
        overview={overview.data}
        windowCount={samples.length}
        onTaskCreated={() => {
          overview.refresh();
          windows.refresh();
        }}
        onTaskStopped={() => {
          overview.refresh();
          windows.refresh();
        }}
      />

      <div style={gridStyle}>
        <div style={{ gridArea: "spectrum" }}>
          <SpectrumPanel taskId={taskId} windowIndex={latestWindowIndex} />
        </div>
        <div style={{ gridArea: "trend" }}>
          <FusionTrend windows={samples} />
        </div>
        <div style={{ gridArea: "state" }}>
          <StateCard overview={overview.data} recentStates={recentStates} />
        </div>
      </div>

      <StatusBar overview={overview.data} lastRefreshAt={lastRefreshAt} backendDown={backendDown} />

      {!taskId && !overview.loading && (
        <div style={emptyHintStyle}>
          {isRunning ? "" : "暂无任务记录,点击右上角"}<strong>"+ 新建任务"</strong>开始监控。
        </div>
      )}
    </div>
  );
}

const pageStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 14,
  minHeight: "calc(100vh - 90px)"
};

const gridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1.2fr) minmax(0, 1fr) minmax(0, 0.8fr)",
  gridTemplateAreas: '"spectrum trend state"',
  gap: 14,
  minHeight: 360
};

const emptyHintStyle: React.CSSProperties = {
  padding: 16,
  background: "#fffbeb",
  border: "1px solid #fde68a",
  borderRadius: 8,
  color: "#92400e",
  textAlign: "center"
};

export default LiveDashboardPage;
