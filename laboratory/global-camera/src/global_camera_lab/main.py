"""Smoke-test CLI for the global camera laboratory project."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import cv2

from .camera import CameraConfig, capture_properties, open_capture, save_frame


@dataclass(frozen=True)
class CameraRequest:
    """Requested capture settings."""

    config: CameraConfig
    warmup_frames: int
    capture_frames: int
    output_dir: Path
    save_frame: bool


@dataclass(frozen=True)
class CaptureSummary:
    """Observed capture information."""

    width: int
    height: int
    fps: float
    brightness: float
    capture_fps: float
    frame_path: Path | None


def parse_args() -> CameraRequest:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Open a camera, read frames, and optionally save one snapshot."
    )
    parser.add_argument("--device", type=int, default=0, help="Camera device index.")
    parser.add_argument(
        "--backend",
        choices=("auto", "v4l2"),
        default="v4l2",
        help="VideoCapture backend on Linux.",
    )
    parser.add_argument(
        "--width", type=int, default=None, help="Requested frame width."
    )
    parser.add_argument(
        "--height", type=int, default=None, help="Requested frame height."
    )
    parser.add_argument("--fps", type=float, default=None, help="Requested camera FPS.")
    parser.add_argument(
        "--fourcc",
        type=str,
        default=None,
        help="Optional FOURCC such as MJPG or YUYV.",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=5,
        help="Frames to discard before collecting summary data.",
    )
    parser.add_argument(
        "--capture-frames",
        type=int,
        default=30,
        help="Frames to read for the smoke test.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("captures"),
        help="Directory for saved snapshots.",
    )
    parser.add_argument(
        "--save-frame",
        action="store_true",
        help="Save the last captured frame to the output directory.",
    )

    args = parser.parse_args()
    if args.warmup_frames < 0:
        raise ValueError("--warmup-frames must be >= 0.")
    if args.capture_frames <= 0:
        raise ValueError("--capture-frames must be > 0.")

    return CameraRequest(
        config=CameraConfig(
            device=args.device,
            backend=args.backend,
            width=args.width,
            height=args.height,
            fps=args.fps,
            fourcc=args.fourcc,
        ),
        warmup_frames=args.warmup_frames,
        capture_frames=args.capture_frames,
        output_dir=args.output_dir,
        save_frame=args.save_frame,
    )


def capture_summary(request: CameraRequest) -> CaptureSummary:
    """Open the device, capture frames, and summarize the result."""

    capture = open_capture(request.config)
    try:
        for _ in range(request.warmup_frames):
            ok, _ = capture.read()
            if not ok:
                raise RuntimeError("Camera warmup failed while reading frames.")

        frame = None
        brightness_total = 0.0
        start = perf_counter()
        for _ in range(request.capture_frames):
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError("Camera capture failed while reading frames.")
            brightness_total += cv2.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))[0]
        duration = perf_counter() - start

        if frame is None:
            raise RuntimeError("No frame was captured from the camera.")

        frame_path = (
            save_frame(frame, request.output_dir) if request.save_frame else None
        )

        return CaptureSummary(
            width=capture_properties(capture)[0],
            height=capture_properties(capture)[1],
            fps=capture_properties(capture)[2],
            brightness=brightness_total / request.capture_frames,
            capture_fps=request.capture_frames / duration if duration > 0 else 0.0,
            frame_path=frame_path,
        )
    finally:
        capture.release()


def print_summary(request: CameraRequest, summary: CaptureSummary) -> None:
    """Print a human-readable capture summary."""

    print(f"Device: {request.config.device}")
    print(f"Backend: {request.config.backend}")
    print(
        "Requested: "
        f"width={request.config.width or 'default'}, "
        f"height={request.config.height or 'default'}, "
        f"fps={request.config.fps or 'default'}, "
        f"fourcc={request.config.fourcc or 'default'}"
    )
    print(
        "Effective: "
        f"width={summary.width}, "
        f"height={summary.height}, "
        f"fps={summary.fps:.2f}"
    )
    print(f"Capture loop FPS: {summary.capture_fps:.2f}")
    print(f"Mean grayscale brightness: {summary.brightness:.2f}")
    if summary.frame_path is not None:
        print(f"Saved frame: {summary.frame_path}")


def main() -> None:
    """Run the smoke-test CLI."""

    request = parse_args()
    summary = capture_summary(request)
    print_summary(request, summary)
