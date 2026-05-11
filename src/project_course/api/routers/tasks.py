"""Task lifecycle routes — /api/v1/tasks/*."""

from __future__ import annotations

import math
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from project_course.api.config import settings
from project_course.api.live import LIVE_STATE, finish_task, get_active_task, start_task
from project_course.api.storage import db
from project_course.api.storage.models import (
    AxisSpectrum,
    CreateTaskRequest,
    TaskDetailResponse,
    TaskResponse,
    TaskWindowsResponse,
    WindowSample,
    WindowSpectraResponse,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.post(
    "",
    summary="Create a sampling + analysis task",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(body: CreateTaskRequest) -> TaskResponse:
    # Auto-stop any active task — creating a new one implies the operator
    # wants to start fresh, not fight a 409. This keeps "+ 新建任务" a
    # one-click reset for demos.
    active = get_active_task()
    if active is not None:
        if db.get_task(active.task_id) is not None:
            finish_task(status="succeeded")
        else:
            # Stale in-memory entry — SQLite has no row for it.
            LIVE_STATE.stop()
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    start_task(
        task_id=task_id,
        device_id=body.device_id,
        window_size_s=body.window_size_s,
        window_hop_s=body.window_hop_s,
        camera_mode=body.camera_mode,
        imu_sample_rate_hz=body.imu_sample_rate_hz,
        roi_x=body.roi_x,
        roi_y=body.roi_y,
        roi_w=body.roi_w,
        roi_h=body.roi_h,
        model_version="sim-baseline-v0" if settings.simulator_enabled else None,
    )
    row = db.get_task(task_id)
    assert row is not None
    return TaskResponse(
        task_id=row["task_id"],
        task_status=row["task_status"],
        created_at=row["created_at"],
    )


@router.post(
    "/{task_id}/stop",
    summary="Stop the currently running task",
    response_model=TaskDetailResponse,
)
def stop_task(task_id: str) -> TaskDetailResponse:
    active = get_active_task()
    if active is None or active.task_id != task_id:
        raise HTTPException(
            status_code=409,
            detail=f"task {task_id} is not currently running",
        )
    finish_task(status="succeeded")
    row = db.get_task(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    return TaskDetailResponse.from_row(row)


@router.get(
    "",
    summary="List recent tasks",
    response_model=list[TaskDetailResponse],
)
def list_tasks(limit: int = Query(default=50, ge=1, le=200)) -> list[TaskDetailResponse]:
    rows = db.list_tasks(limit=limit)
    return [TaskDetailResponse.from_row(r) for r in rows]


@router.get(
    "/{task_id}",
    summary="Get task status and result summary",
    response_model=TaskDetailResponse,
)
def get_task(task_id: str) -> TaskDetailResponse:
    row = db.get_task(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    return TaskDetailResponse.from_row(row)


@router.get(
    "/{task_id}/windows",
    summary="List all window samples for a task",
    response_model=TaskWindowsResponse,
)
def get_task_windows(task_id: str) -> TaskWindowsResponse:
    if db.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    rows = db.list_windows(task_id)
    samples = [WindowSample.model_validate(_clean_nan(r)) for r in rows]
    return TaskWindowsResponse(task_id=task_id, samples=samples)


@router.get(
    "/{task_id}/spectra",
    summary="Get per-axis spectrum curves for one window (stub: synthesized from features)",
    response_model=WindowSpectraResponse,
)
def get_task_spectra(
    task_id: str,
    window_index: int = Query(..., ge=0),
) -> WindowSpectraResponse:
    if db.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    payload = db.get_window(task_id, window_index)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"window {window_index} of task {task_id} not found",
        )

    def axis(peak_hz_key: str, peak_power_key: str) -> AxisSpectrum | None:
        peak = payload.get(peak_hz_key)
        power = payload.get(peak_power_key, 1.0) or 1.0
        if peak is None:
            return None
        return _synthesize_spectrum(float(peak), float(power))

    return WindowSpectraResponse(
        task_id=task_id,
        window_index=window_index,
        vision_dx=axis("vision_dx_peak_hz", "vision_dx_peak_power"),
        vision_dy=axis("vision_dy_peak_hz", "vision_dy_peak_power"),
        sensor_ax=axis("sensor_ax_peak_hz", "sensor_ax_peak_power"),
        sensor_ay=axis("sensor_ay_peak_hz", "sensor_ay_peak_power"),
        sensor_az=axis("sensor_az_peak_hz", "sensor_az_peak_power"),
        sensor_gx=axis("sensor_gx_peak_hz", "sensor_gx_peak_power"),
        sensor_gy=axis("sensor_gy_peak_hz", "sensor_gy_peak_power"),
        sensor_gz=axis("sensor_gz_peak_hz", "sensor_gz_peak_power"),
    )


# --------------------------- helpers ---------------------------------------

def _clean_nan(record: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for k, v in record.items():
        if isinstance(v, float) and math.isnan(v):
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def _synthesize_spectrum(peak_hz: float, peak_power: float, *, n: int = 64, max_hz: float = 200.0) -> AxisSpectrum:
    """Build a single-peak gaussian spectrum so the dashboard can render a curve.

    Real spectrum arrays will be supplied by the feature pipeline; until then,
    this stub keeps the chart populated without lying about the dominant
    frequency (which is the only quantitatively correct value displayed).
    """
    freqs = [round(i * (max_hz / (n - 1)), 3) for i in range(n)]
    sigma = max(2.0, peak_hz * 0.05)
    powers = [
        round(float(peak_power) * math.exp(-((f - peak_hz) ** 2) / (2 * sigma ** 2)), 6)
        for f in freqs
    ]
    return AxisSpectrum(freq_hz=freqs, power=powers)
