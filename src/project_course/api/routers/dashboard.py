"""Dashboard overview APIs."""

from __future__ import annotations

from fastapi import APIRouter

from project_course.services.runtime_state import (
    task_results,
    task_store,
    task_windows,
    update_reports,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/overview", summary="大屏概览数据")
def get_dashboard_overview() -> dict[str, object]:
    """Return overview payload from shared runtime state."""

    latest_task = None
    if task_results:
        latest_task = list(task_results.keys())[-1]

    latest_status = "pending"
    latest_state = "unknown"
    latest_freq = 0.0
    model_version = "v0.0.0"

    if latest_task is not None:
        task = task_store.get_task(latest_task)
        result = task_results.get(latest_task, {})
        windows = task_windows.get(latest_task, [])
        latest_status = task.task_status if task else "pending"
        latest_state = str(result.get("predicted_state", "unknown"))
        model_version = str(result.get("model_version", "v0.0.0"))
        if windows:
            latest_freq = float(windows[-1].get("fused_dominant_freq_hz", 0.0))

    rows = task_store._tasks.values()
    success_count = sum(1 for row in rows if row.task_status == "succeeded")
    total_count = len(task_store._tasks)
    success_rate = (success_count / total_count) if total_count else 0.0

    payload = {
        "latest_task_id": latest_task or "task-placeholder",
        "latest_status": latest_status,
        "latest_predicted_state": latest_state,
        "latest_fused_frequency_hz": latest_freq,
        "active_model_version": model_version,
        "task_success_rate_24h": success_rate,
        "sync_offset_ms_p95": 1.0,
    }
    if update_reports:
        payload["latest_incremental_report"] = update_reports[-1]
    return payload
