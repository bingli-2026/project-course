"""Configuration values for the FastAPI service."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PROJECT_COURSE_",
    )

    app_name: str = "project-course-api"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False

    # Sampling defaults
    default_window_size_s: float = 0.25
    default_window_hop_s: float = 0.05
    default_imu_sample_rate_hz: int = 480

    # Optional fallback ROI if request payload does not provide one
    default_roi_x: int = 0
    default_roi_y: int = 0
    default_roi_w: int = 160
    default_roi_h: int = 140

    # Time sync thresholds
    sync_fit_window_s: float = 4.0
    sync_refit_interval_s: float = 1.0
    sync_fit_r2_threshold: float = 0.995

    # Runtime guards
    imu_stream_timeout_ms: int = 500
    camera_gap_multiplier: float = 3.0
    disk_guard_ratio: float = 1.5
    imu_source_mode: str = "auto"  # auto | live | synthetic
    imu_serial_port: str = "/dev/ttyACM0"
    imu_serial_baudrate: int = 921600
    imu_capture_windows: int = 8
    imu_handshake_retry_count: int = 20
    imu_handshake_timeout_ms: int = 500

    # Incremental update guard
    incremental_min_windows: int = 90
    incremental_min_sessions: int = 3


settings = Settings()
