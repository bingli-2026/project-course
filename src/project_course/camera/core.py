"""Camera capture helpers shared by the main project package."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import cv2


@dataclass(frozen=True)
class CameraConfig:
    """Requested settings for opening a camera device."""

    device: int = 0
    backend: str = "v4l2"
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    fourcc: str | None = None


@dataclass(frozen=True)
class CaptureSummary:
    """Observed capture information from a probe run."""

    width: int
    height: int
    fps: float
    brightness: float
    capture_fps: float
    frame_path: Path | None


def validate_fourcc(fourcc: str | None) -> None:
    """Validate a FOURCC string when provided."""

    if fourcc is not None and len(fourcc) != 4:
        raise ValueError("FOURCC must be exactly 4 characters.")


def backend_flag(backend: str) -> int:
    """Map a backend choice to an OpenCV backend flag."""

    return cv2.CAP_V4L2 if backend == "v4l2" else cv2.CAP_ANY


def configure_capture(capture: cv2.VideoCapture, config: CameraConfig) -> None:
    """Apply requested camera settings to an open capture device."""

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


def save_frame(frame: Any, output_dir: Path) -> Path:
    """Persist a captured frame to disk."""

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    frame_path = output_dir / f"snapshot-{timestamp}.png"
    if not cv2.imwrite(str(frame_path), frame):
        raise RuntimeError(f"Failed to save frame to {frame_path}")
    return frame_path


def probe_capture(
    config: CameraConfig,
    *,
    warmup_frames: int = 5,
    capture_frames: int = 30,
    output_dir: Path = Path("captures"),
    save_snapshot: bool = False,
) -> CaptureSummary:
    """Open a camera, read a short burst of frames, and summarize the result."""

    if warmup_frames < 0:
        raise ValueError("warmup_frames must be >= 0.")
    if capture_frames <= 0:
        raise ValueError("capture_frames must be > 0.")

    capture = open_capture(config)
    try:
        for _ in range(warmup_frames):
            ok, _ = capture.read()
            if not ok:
                raise RuntimeError("Camera warmup failed while reading frames.")

        frame = None
        brightness_total = 0.0
        start = perf_counter()
        for _ in range(capture_frames):
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError("Camera capture failed while reading frames.")
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness_total += cv2.mean(gray)[0]
        duration = perf_counter() - start

        if frame is None:
            raise RuntimeError("No frame was captured from the camera.")

        width, height, fps = capture_properties(capture)
        frame_path = save_frame(frame, output_dir) if save_snapshot else None
        return CaptureSummary(
            width=width,
            height=height,
            fps=fps,
            brightness=brightness_total / capture_frames,
            capture_fps=capture_frames / duration if duration > 0 else 0.0,
            frame_path=frame_path,
        )
    finally:
        capture.release()
