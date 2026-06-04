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
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

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


settings = Settings()
