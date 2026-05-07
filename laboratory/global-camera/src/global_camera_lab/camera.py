"""Shared camera helpers for the global camera laboratory project."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2


@dataclass(frozen=True)
class CameraConfig:
    """Requested camera settings shared by CLI tools."""

    device: int
    backend: str
    width: int | None
    height: int | None
    fps: float | None
    fourcc: str | None


def validate_fourcc(fourcc: str | None) -> None:
    """Validate a FOURCC string when provided."""

    if fourcc is not None and len(fourcc) != 4:
        raise ValueError("--fourcc must be exactly 4 characters.")


def backend_flag(backend: str) -> int:
    """Map the CLI backend choice to an OpenCV backend flag."""

    return cv2.CAP_V4L2 if backend == "v4l2" else cv2.CAP_ANY


def configure_capture(capture: cv2.VideoCapture, config: CameraConfig) -> None:
    """Apply requested camera settings."""

    if config.width is not None:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
    if config.height is not None:
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)
    if config.fps is not None:
        capture.set(cv2.CAP_PROP_FPS, config.fps)
    if config.fourcc is not None:
        capture.set(
            cv2.CAP_PROP_FOURCC,
            cv2.VideoWriter_fourcc(*config.fourcc),
        )


def open_capture(config: CameraConfig) -> cv2.VideoCapture:
    """Open a camera device with the requested settings."""

    validate_fourcc(config.fourcc)

    capture = cv2.VideoCapture(config.device, backend_flag(config.backend))
    if not capture.isOpened():
        raise RuntimeError(
            f"Failed to open camera device {config.device} using backend "
            f"{config.backend}."
        )

    configure_capture(capture, config)
    return capture


def capture_properties(capture: cv2.VideoCapture) -> tuple[int, int, float]:
    """Return the effective width, height, and FPS of an open capture."""

    return (
        int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        float(capture.get(cv2.CAP_PROP_FPS)),
    )


def save_frame(frame, output_dir: Path) -> Path:
    """Persist a captured frame to disk."""

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    frame_path = output_dir / f"snapshot-{timestamp}.png"
    if not cv2.imwrite(str(frame_path), frame):
        raise RuntimeError(f"Failed to save frame to {frame_path}")
    return frame_path
