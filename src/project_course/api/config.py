"""Configuration values for the FastAPI service."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


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

    # Storage
    data_dir: Path = _REPO_ROOT / "data" / "samples"
    db_path: Path = _REPO_ROOT / "data" / "project_course.sqlite3"

    # CORS
    cors_origins: list[str] = ["*"]
    cors_origin_regex: str | None = None
    cors_allow_credentials: bool = False

    # Deployment defaults confirmed on orangepiaipro-20t for ~20 Hz machinery.
    window_size_s: float = 0.5
    window_hop_s: float = 0.25
    imu_sample_rate_hz: int = 400
    camera_mode: str = "YUYV_640x480_400fps"
    analysis_fps: float = 400.0

    # Live state buffer
    window_buffer_size: int = 240  # ~2 minutes at 0.5s hop

    # Simulator (used when no real feature pipeline is attached)
    simulator_enabled: bool = True
    simulator_tick_s: float = 0.5  # one synthetic window every 0.5s wall-clock

    # Real live capture pipeline (used on the Orange Pi demo device)
    real_pipeline_enabled: bool = False
    real_camera_index: int = 0
    real_camera_width: int = 640
    real_camera_height: int = 480
    real_camera_fps: int = 400
    real_camera_fourcc: str = "YUYV"
    real_capture_buffer_s: float = 6.0
    real_analysis_poll_s: float = 0.01
    real_visual_min_frequency_hz: float = 1.0
    real_visual_max_frequency_hz: float = 80.0
    real_visual_max_corners: int = 80
    real_visual_use_clahe: bool = True
    real_imu_bus_id: int = 7
    real_imu_address: int = 0x6A
    real_include_gyro: bool = False


settings = Settings()
