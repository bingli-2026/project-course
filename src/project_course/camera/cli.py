"""Command-line tools for the mainline camera package."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .core import CameraConfig, CaptureSummary, probe_capture
from .v4l2 import (
    V4L2Device,
    VideoNodeLink,
    discover_video_links,
    discover_video_nodes,
    list_v4l2_devices,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level camera CLI parser."""

    parser = argparse.ArgumentParser(
        description="Mainline camera tools for device discovery and probing."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available V4L2 devices and video nodes.")

    probe_parser = subparsers.add_parser(
        "probe",
        help="Open a camera, read a short burst of frames, and print the result.",
    )
    probe_parser.add_argument("--device", type=int, default=0, help="Camera index.")
    probe_parser.add_argument(
        "--backend",
        choices=("auto", "v4l2"),
        default="v4l2",
        help="VideoCapture backend on Linux.",
    )
    probe_parser.add_argument(
        "--width", type=int, default=None, help="Requested frame width."
    )
    probe_parser.add_argument(
        "--height", type=int, default=None, help="Requested frame height."
    )
    probe_parser.add_argument("--fps", type=float, default=None, help="Requested FPS.")
    probe_parser.add_argument(
        "--fourcc",
        type=str,
        default=None,
        help="Optional FOURCC such as MJPG or YUYV.",
    )
    probe_parser.add_argument(
        "--warmup-frames",
        type=int,
        default=5,
        help="Frames to discard before collecting summary data.",
    )
    probe_parser.add_argument(
        "--capture-frames",
        type=int,
        default=30,
        help="Frames to read for the probe run.",
    )
    probe_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("captures"),
        help="Directory for saved snapshots.",
    )
    probe_parser.add_argument(
        "--save-frame",
        action="store_true",
        help="Save the last captured frame to the output directory.",
    )
    return parser


def format_requested_value(value: int | float | str | None) -> str:
    """Format optional configuration values for human-readable output."""

    return str(value) if value is not None else "default"


def print_v4l2_devices(devices: list[V4L2Device]) -> None:
    """Print named V4L2 devices."""

    if not devices:
        print("No named V4L2 devices found.")
        return

    print("V4L2 devices:")
    for device in devices:
        bus = f" ({device.bus_info})" if device.bus_info is not None else ""
        nodes = ", ".join(str(node) for node in device.video_nodes)
        print(f"- {device.name}{bus}: {nodes or 'no /dev/video nodes'}")


def print_video_links(links: list[VideoNodeLink]) -> None:
    """Print stable `/dev/v4l/by-id` aliases when present."""

    if not links:
        print("Video links: none")
        return

    print("Video links:")
    for link in links:
        print(f"- {link.alias} -> {link.target}")


def print_video_nodes(nodes: list[Path]) -> None:
    """Print raw `/dev/video*` nodes."""

    if not nodes:
        print("Video nodes: none")
        return

    print("Video nodes:")
    for node in nodes:
        print(f"- {node}")


def run_list_command() -> None:
    """Run the `list` subcommand."""

    try:
        devices = list_v4l2_devices()
    except RuntimeError as error:
        print(f"V4L2 device names unavailable: {error}")
    else:
        print_v4l2_devices(devices)

    print_video_links(discover_video_links())
    print_video_nodes(discover_video_nodes())


def print_probe_summary(config: CameraConfig, summary: CaptureSummary) -> None:
    """Print the results of a camera probe run."""

    print(f"Device: {config.device}")
    print(f"Backend: {config.backend}")
    print(
        "Requested: "
        f"width={format_requested_value(config.width)}, "
        f"height={format_requested_value(config.height)}, "
        f"fps={format_requested_value(config.fps)}, "
        f"fourcc={format_requested_value(config.fourcc)}"
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


def run_probe_command(args: argparse.Namespace) -> None:
    """Run the `probe` subcommand."""

    config = CameraConfig(
        device=args.device,
        backend=args.backend,
        width=args.width,
        height=args.height,
        fps=args.fps,
        fourcc=args.fourcc,
    )
    summary = probe_capture(
        config,
        warmup_frames=args.warmup_frames,
        capture_frames=args.capture_frames,
        output_dir=args.output_dir,
        save_snapshot=args.save_frame,
    )
    print_probe_summary(config, summary)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the mainline camera CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list":
        run_list_command()
        return
    if args.command == "probe":
        run_probe_command(args)
        return
    raise RuntimeError(f"Unsupported camera command: {args.command}")
