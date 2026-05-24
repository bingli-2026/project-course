"""Task lifecycle routes — /api/v1/tasks/*."""

from __future__ import annotations

import logging
import math
import uuid
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from project_course.api.config import settings
from project_course.api.live import (
    LIVE_STATE,
    finish_task,
    get_active_task,
    publish_window,
    record_sync_quality,
    start_task,
)
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
from project_course.services.error_codes import IMU_STREAM_TIMEOUT
from project_course.services.runtime_state import model_registry

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)


@router.post(
    "",
    summary="Create a sampling + analysis task",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(body: CreateTaskRequest) -> TaskResponse:
    if not body.device_id.strip():
        raise HTTPException(status_code=400, detail="device_id is required")

    active = get_active_task()
    if active is not None:
        if db.get_task(active.task_id) is not None:
            finish_task(status="succeeded")
        else:
            LIVE_STATE.stop()

    if model_registry.latest() is None:
        model_registry.add_version("v0.1.0", "baseline")
    latest_model = model_registry.latest()

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
        model_version=(
            latest_model.model_version
            if latest_model is not None
            else ("sim-baseline-v0" if settings.simulator_enabled else None)
        ),
    )

    if settings.capture_on_create:
        _collect_task_windows(task_id, body)

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
def list_tasks(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[TaskDetailResponse]:
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
    summary=(
        "Get per-axis spectrum curves for one window "
        "(stub: synthesized from features)"
    ),
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


def _clean_nan(record: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, float) and math.isnan(value):
            cleaned[key] = None
        else:
            cleaned[key] = value
    return cleaned


def _synthesize_spectrum(
    peak_hz: float,
    peak_power: float,
    *,
    n: int = 64,
    max_hz: float = 200.0,
) -> AxisSpectrum:
    freqs = [round(i * (max_hz / (n - 1)), 3) for i in range(n)]
    sigma = max(2.0, peak_hz * 0.05)
    powers = [
        round(
            float(peak_power) * math.exp(-((freq - peak_hz) ** 2) / (2 * sigma**2)),
            6,
        )
        for freq in freqs
    ]
    return AxisSpectrum(freq_hz=freqs, power=powers)


def _collect_task_windows(task_id: str, body: CreateTaskRequest) -> None:
    from project_course.services.capture_service import CaptureRequest

    request = CaptureRequest(
        device_id=body.device_id,
        camera_mode=body.camera_mode or settings.camera_mode,
        imu_sample_rate_hz=body.imu_sample_rate_hz or settings.imu_sample_rate_hz,
        window_size_s=body.window_size_s or settings.window_size_s,
        window_hop_s=body.window_hop_s or settings.window_hop_s,
        roi_x=body.roi_x,
        roi_y=body.roi_y,
        roi_w=body.roi_w,
        roi_h=body.roi_h,
    )

    try:
        windows, vectors = _capture_service().run_capture_pipeline(
            request,
            task_id=task_id,
        )
    except RuntimeError as exc:
        message = str(exc)
        logger.exception("capture pipeline runtime error: %s", message)
        finish_task(status="failed", error_message=message)
        if message.startswith(f"{IMU_STREAM_TIMEOUT.code}:"):
            raise HTTPException(
                status_code=503,
                detail={
                    "code": IMU_STREAM_TIMEOUT.code,
                    "message": IMU_STREAM_TIMEOUT.message,
                    "action": IMU_STREAM_TIMEOUT.action,
                },
            ) from exc
        raise HTTPException(status_code=500, detail=message) from exc
    except Exception as exc:
        logger.exception("capture pipeline unexpected error")
        finish_task(status="failed", error_message=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    for window in windows:
        publish_window(
            {key: value for key, value in window.items() if key != "_spectra"}
        )

    infer = _inference_service().predict(vectors)
    if windows:
        aligned_count = sum(
            1 for row in windows if not row.get("sync_fit_failed", False)
        )
        aligned_ratio = aligned_count / len(windows)
        record_sync_quality(
            offset_ms_p95=1.0,
            drift_ppm=3.0,
            aligned_window_ratio=aligned_ratio,
        )

    latest_model = model_registry.latest()
    db.update_task(
        task_id,
        {
            "predicted_state": infer.predicted_state,
            "confidence_summary": infer.confidence_summary,
            "effective_window_count": len(windows),
            "model_version": (
                latest_model.model_version if latest_model is not None else None
            ),
        },
    )
    finish_task(status="succeeded")


@lru_cache(maxsize=1)
def _capture_service():
    from project_course.services.capture_service import CaptureService

    return CaptureService()


@lru_cache(maxsize=1)
def _inference_service():
    from project_course.services.inference_service import InferenceService

    return InferenceService()
