"""Dashboard overview — /api/v1/dashboard/overview."""

from __future__ import annotations

from fastapi import APIRouter

from project_course.api.live import LIVE_STATE
from project_course.api.storage import db
from project_course.api.storage.models import DashboardOverview

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/overview", summary="Top-of-screen dashboard summary", response_model=DashboardOverview)
def get_overview() -> DashboardOverview:
    row = db.latest_task()
    if row is None:
        return DashboardOverview(task_success_rate_24h=db.task_success_rate_24h())

    buffer = LIVE_STATE.snapshot_buffer()
    latest_window = buffer[-1] if buffer else None

    return DashboardOverview(
        latest_task_id=row["task_id"],
        latest_status=row["task_status"],
        latest_predicted_state=row["predicted_state"],
        latest_fused_frequency_hz=(latest_window or {}).get("fused_dominant_freq_hz"),
        active_model_version=row["model_version"],
        task_success_rate_24h=db.task_success_rate_24h(),
        sync_offset_ms_p95=row["sync_offset_ms_p95"],
        aligned_window_ratio=row["aligned_window_ratio"],
        effective_window_count=row["effective_window_count"] or 0,
        latest_window_index=(latest_window or {}).get("window_index"),
    )
