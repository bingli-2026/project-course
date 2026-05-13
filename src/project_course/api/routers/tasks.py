"""Task APIs for capture orchestration and window-level retrieval."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from project_course.services.capture_service import CaptureRequest, CaptureService
from project_course.services.inference_service import InferenceService
from project_course.services.runtime_state import (
    model_registry,
    task_results,
    task_store,
    task_windows,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

_capture_service = CaptureService()
_inference_service = InferenceService()


class CreateTaskRequest(BaseModel):
    device_id: str
    camera_mode: str = "YUY2_160x140_420fps"
    imu_sample_rate_hz: int = 1680
    window_size_s: float = 0.25
    window_hop_s: float = 0.05
    roi_x: int | None = None
    roi_y: int | None = None
    roi_w: int | None = None
    roi_h: int | None = None


@router.post("", summary="创建采样与分析任务")
def create_task(payload: CreateTaskRequest) -> dict[str, object]:
    """Create one task and run a synthetic US1 capture/inference pipeline."""

    if not payload.device_id.strip():
        raise HTTPException(status_code=400, detail="device_id is required")

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    task_store.create_task(task_id=task_id, device_id=payload.device_id)
    task_store.update_status(task_id, "running")

    request = CaptureRequest(**payload.model_dump())
    windows, vectors = _capture_service.run_capture_pipeline(request, task_id=task_id)

    infer = _inference_service.predict(vectors)
    task_windows[task_id] = windows

    if model_registry.latest() is None:
        model_registry.add_version("v0.1.0", "baseline")
    latest_model = model_registry.latest()

    task_results[task_id] = {
        "predicted_state": infer.predicted_state,
        "confidence_summary": infer.confidence_summary,
        "effective_window_count": len(windows),
        "model_version": latest_model.model_version if latest_model else "v0.1.0",
    }

    task_store.update_status(task_id, "succeeded")
    task = task_store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=500, detail="task creation failed")

    return {
        "task_id": task.task_id,
        "task_status": task.task_status,
        "created_at": task.created_at,
    }


@router.get("/{task_id}", summary="查询任务状态与结果摘要")
def get_task(task_id: str) -> dict[str, object]:
    """Return task status and inference summary."""

    task = task_store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")

    result = task_results.get(
        task_id,
        {
            "predicted_state": "unknown",
            "confidence_summary": 0.0,
            "effective_window_count": 0,
            "model_version": "v0.1.0",
        },
    )
    windows = task_windows.get(task_id, [])
    aligned = 0.0
    if windows:
        ok_count = sum(1 for row in windows if not row.get("sync_fit_failed", False))
        aligned = ok_count / len(windows)

    return {
        "task_id": task.task_id,
        "task_status": task.task_status,
        "model_version": result["model_version"],
        "predicted_state": result["predicted_state"],
        "confidence_summary": result["confidence_summary"],
        "effective_window_count": result["effective_window_count"],
        "sync_quality": {
            "offset_ms_p95": 1.0,
            "drift_ppm": 3.0,
            "aligned_window_ratio": aligned,
        },
    }


@router.get("/{task_id}/windows", summary="查询窗口级分轴特征")
def get_task_windows(task_id: str) -> dict[str, object]:
    """Return window-level features for one task."""

    if task_id not in task_windows:
        raise HTTPException(status_code=404, detail="task windows not found")

    samples: list[dict[str, object]] = []
    for row in task_windows[task_id]:
        out = {k: v for k, v in row.items() if k != "_spectra"}
        samples.append(out)
    return {"task_id": task_id, "samples": samples}


@router.get("/{task_id}/spectra", summary="查询窗口级频谱曲线")
def get_task_spectra(task_id: str, window_index: int) -> dict[str, object]:
    """Return per-axis spectra for one task window."""

    windows = task_windows.get(task_id)
    if windows is None:
        raise HTTPException(status_code=404, detail="task windows not found")
    if window_index < 0 or window_index >= len(windows):
        raise HTTPException(status_code=404, detail="window not found")

    spectra = windows[window_index].get("_spectra")
    if not isinstance(spectra, dict):
        raise HTTPException(status_code=404, detail="spectra not found")

    return {
        "task_id": task_id,
        "window_index": window_index,
        **spectra,
    }
