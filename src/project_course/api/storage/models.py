"""Pydantic response models for the API."""

from __future__ import annotations

import sqlite3
from typing import Any, Literal

from pydantic import BaseModel, Field

TaskStatus = Literal["pending", "running", "succeeded", "failed"]


class CreateTaskRequest(BaseModel):
    device_id: str
    camera_mode: str | None = None
    imu_sample_rate_hz: int | None = None
    window_size_s: float | None = None
    window_hop_s: float | None = None
    roi_x: int | None = None
    roi_y: int | None = None
    roi_w: int | None = None
    roi_h: int | None = None


class TaskResponse(BaseModel):
    task_id: str
    task_status: TaskStatus
    created_at: str


class SyncQuality(BaseModel):
    offset_ms_p95: float | None = None
    drift_ppm: float | None = None
    aligned_window_ratio: float | None = None


class TaskDetailResponse(BaseModel):
    task_id: str
    task_status: TaskStatus
    device_id: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    camera_mode: str
    imu_sample_rate_hz: int
    window_size_s: float
    window_hop_s: float
    roi_x: int | None = None
    roi_y: int | None = None
    roi_w: int | None = None
    roi_h: int | None = None
    model_version: str | None = None
    predicted_state: str | None = None
    confidence_summary: float | None = None
    effective_window_count: int = 0
    sync_quality: SyncQuality = Field(default_factory=SyncQuality)
    error_message: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TaskDetailResponse":
        return cls(
            task_id=row["task_id"],
            task_status=row["task_status"],
            device_id=row["device_id"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            camera_mode=row["camera_mode"],
            imu_sample_rate_hz=row["imu_sample_rate_hz"],
            window_size_s=row["window_size_s"],
            window_hop_s=row["window_hop_s"],
            roi_x=row["roi_x"],
            roi_y=row["roi_y"],
            roi_w=row["roi_w"],
            roi_h=row["roi_h"],
            model_version=row["model_version"],
            predicted_state=row["predicted_state"],
            confidence_summary=row["confidence_summary"],
            effective_window_count=row["effective_window_count"] or 0,
            sync_quality=SyncQuality(
                offset_ms_p95=row["sync_offset_ms_p95"],
                drift_ppm=row["sync_drift_ppm"],
                aligned_window_ratio=row["aligned_window_ratio"],
            ),
            error_message=row["error_message"],
        )


class WindowSample(BaseModel):
    """Window-level feature row. Schema-aligned with doc/feature_schema.md."""

    sample_id: str
    window_index: int
    center_time_s: float
    label: str | None = None
    modality: str | None = None
    imu_quality_flag: str | None = None
    cam_quality_flag: str | None = None
    sync_fit_failed: bool | None = None
    seq_gap_count: int | None = None

    # Allow arbitrary vision_*/sensor_*/fused_* fields without listing all of them.
    model_config = {"extra": "allow"}


class TaskWindowsResponse(BaseModel):
    task_id: str
    samples: list[WindowSample] = Field(default_factory=list)


class AxisSpectrum(BaseModel):
    freq_hz: list[float]
    power: list[float]


class WindowSpectraResponse(BaseModel):
    task_id: str
    window_index: int
    vision_dx: AxisSpectrum | None = None
    vision_dy: AxisSpectrum | None = None
    sensor_ax: AxisSpectrum | None = None
    sensor_ay: AxisSpectrum | None = None
    sensor_az: AxisSpectrum | None = None
    sensor_gx: AxisSpectrum | None = None
    sensor_gy: AxisSpectrum | None = None
    sensor_gz: AxisSpectrum | None = None


class DashboardOverview(BaseModel):
    latest_task_id: str | None = None
    latest_status: TaskStatus | None = None
    latest_predicted_state: str | None = None
    latest_fused_frequency_hz: float | None = None
    active_model_version: str | None = None
    task_success_rate_24h: float = 1.0
    sync_offset_ms_p95: float | None = None
    sync_drift_ppm: float | None = None
    aligned_window_ratio: float | None = None
    effective_window_count: int = 0
    latest_window_index: int | None = None


# ---------- offline history models (renamed from v0 SampleMetadata) --------


class HistoryMetadata(BaseModel):
    sample_id: str
    label: str | None = None
    captured_at: str | None = None
    source_name: str | None = None
    has_vision: bool
    has_sensor: bool
    file_path: str
    window_count: int
    ingested_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "HistoryMetadata":
        return cls(
            sample_id=row["sample_id"],
            label=row["label"],
            captured_at=row["captured_at"],
            source_name=row["source_name"],
            has_vision=bool(row["has_vision"]),
            has_sensor=bool(row["has_sensor"]),
            file_path=row["file_path"],
            window_count=row["window_count"],
            ingested_at=row["ingested_at"],
        )


class HistoryDetail(BaseModel):
    metadata: HistoryMetadata
    rows: list[dict[str, Any]] = Field(default_factory=list)


class HistoryTimeseries(BaseModel):
    sample_id: str
    fields: list[str]
    points: list[dict[str, Any]] = Field(default_factory=list)
