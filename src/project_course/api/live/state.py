"""Live in-memory state for the currently monitored task.

Single-process, single-task assumption for the midterm demo. If we later need
multi-task or multi-process, replace `LiveState` with a Redis-backed
implementation but keep the same call surface.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from project_course.api.config import settings
from project_course.api.storage import db


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class LiveTask:
    task_id: str
    device_id: str
    window_size_s: float
    window_hop_s: float


@dataclass
class LiveState:
    """Thread-safe holder for the currently active task and its window buffer."""

    active_task: LiveTask | None = None
    buffer: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=settings.window_buffer_size))
    sync_quality: dict[str, float] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def start(self, task: LiveTask) -> None:
        with self._lock:
            self.active_task = task
            self.buffer.clear()
            self.sync_quality.clear()

    def stop(self) -> None:
        with self._lock:
            self.active_task = None

    def publish(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self.buffer.append(payload)

    def update_sync_quality(self, **metrics: float) -> None:
        with self._lock:
            for key, value in metrics.items():
                if value is not None:
                    self.sync_quality[key] = value

    def snapshot_buffer(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.buffer)

    def snapshot_sync_quality(self) -> dict[str, float]:
        with self._lock:
            return dict(self.sync_quality)


LIVE_STATE = LiveState()


# --------------------------- public api ------------------------------------

def start_task(
    task_id: str,
    device_id: str,
    *,
    window_size_s: float | None = None,
    window_hop_s: float | None = None,
    camera_mode: str | None = None,
    imu_sample_rate_hz: int | None = None,
    roi_x: int | None = None,
    roi_y: int | None = None,
    roi_w: int | None = None,
    roi_h: int | None = None,
    model_version: str | None = None,
) -> None:
    """Persist a new task and mark it active in the live buffer."""
    ws = window_size_s if window_size_s is not None else settings.window_size_s
    wh = window_hop_s if window_hop_s is not None else settings.window_hop_s

    db.insert_task(
        {
            "task_id": task_id,
            "task_status": "running",
            "created_at": _now_iso(),
            "started_at": _now_iso(),
            "finished_at": None,
            "device_id": device_id,
            "camera_mode": camera_mode or settings.camera_mode,
            "imu_sample_rate_hz": imu_sample_rate_hz or settings.imu_sample_rate_hz,
            "window_size_s": ws,
            "window_hop_s": wh,
            "roi_x": roi_x,
            "roi_y": roi_y,
            "roi_w": roi_w,
            "roi_h": roi_h,
            "model_version": model_version,
            "predicted_state": None,
            "confidence_summary": None,
            "effective_window_count": 0,
            "sync_offset_ms_p95": None,
            "sync_drift_ppm": None,
            "aligned_window_ratio": None,
            "error_message": None,
        }
    )
    LIVE_STATE.start(LiveTask(task_id=task_id, device_id=device_id, window_size_s=ws, window_hop_s=wh))


def publish_window(payload: dict[str, Any]) -> None:
    """Push a window sample into the live buffer and persist it.

    `payload` MUST contain at least `sample_id`, `window_index`, `center_time_s`.
    The current task's prediction summary (predicted_state, confidence_summary,
    effective_window_count) is updated from the payload's `predicted_state` and
    `prediction_confidence` fields when present.
    """
    task = LIVE_STATE.active_task
    if task is None:
        return  # silently drop windows when no task is active
    LIVE_STATE.publish(payload)
    db.insert_window(task.task_id, int(payload["window_index"]), payload)

    updates: dict[str, Any] = {"effective_window_count": len(LIVE_STATE.snapshot_buffer())}
    if "predicted_state" in payload:
        updates["predicted_state"] = payload["predicted_state"]
    if "prediction_confidence" in payload:
        try:
            updates["confidence_summary"] = float(payload["prediction_confidence"])
        except (TypeError, ValueError):
            pass
    db.update_task(task.task_id, updates)


def record_sync_quality(
    offset_ms_p95: float | None = None,
    drift_ppm: float | None = None,
    aligned_window_ratio: float | None = None,
) -> None:
    """Record sync quality metrics for the currently active task."""
    task = LIVE_STATE.active_task
    if task is None:
        return
    LIVE_STATE.update_sync_quality(
        offset_ms_p95=offset_ms_p95,
        drift_ppm=drift_ppm,
        aligned_window_ratio=aligned_window_ratio,
    )
    db.update_task(
        task.task_id,
        {
            "sync_offset_ms_p95": offset_ms_p95,
            "sync_drift_ppm": drift_ppm,
            "aligned_window_ratio": aligned_window_ratio,
        },
    )


def finish_task(*, status: str = "succeeded", error_message: str | None = None) -> None:
    """Mark the active task as finished and detach it from the live buffer."""
    task = LIVE_STATE.active_task
    if task is None:
        return
    db.update_task(
        task.task_id,
        {
            "task_status": status,
            "finished_at": _now_iso(),
            "error_message": error_message,
        },
    )
    LIVE_STATE.stop()


def get_active_task() -> LiveTask | None:
    return LIVE_STATE.active_task


def get_recent_windows() -> list[dict[str, Any]]:
    return LIVE_STATE.snapshot_buffer()
