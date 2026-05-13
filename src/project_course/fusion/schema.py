"""Schema-aligned models for window-level multimodal features."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WindowIdentity(BaseModel):
    """Shared identity fields aligned with doc/feature_schema.md."""

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    label: str
    modality: str
    source_name: str
    window_index: int = Field(ge=0)
    window_start_frame: int = Field(ge=0)
    window_end_frame: int = Field(ge=0)
    center_time_s: float
    analysis_fps: float = Field(gt=0)


class QualityFlags(BaseModel):
    """Window quality flags and sync diagnostics."""

    model_config = ConfigDict(extra="forbid")

    imu_quality_flag: str = "ok"
    cam_quality_flag: str = "ok"
    sync_fit_failed: bool = False
    seq_gap_count: int = Field(default=0, ge=0)


class WindowSample(WindowIdentity, QualityFlags):
    """Minimal foundational window sample model.

    Full per-axis feature fields will be progressively populated in US1 tasks.
    """

    roi_x: int | None = None
    roi_y: int | None = None
    roi_w: int | None = None
    roi_h: int | None = None
    fused_dominant_freq_hz: float | None = None
    fusion_confidence: float | None = Field(default=None, ge=0, le=1)
