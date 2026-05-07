"""V4L2 device discovery helpers for Linux camera workflows."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class V4L2Device:
    """A named V4L2 device with one or more video nodes."""

    name: str
    bus_info: str | None
    video_nodes: tuple[Path, ...]


@dataclass(frozen=True)
class VideoNodeLink:
    """A symbolic link that points at a video node."""

    alias: Path
    target: Path


def parse_v4l2_device_listing(text: str) -> list[V4L2Device]:
    """Parse `v4l2-ctl --list-devices` output into structured devices."""

    devices: list[V4L2Device] = []
    current_name: str | None = None
    current_bus_info: str | None = None
    current_nodes: list[Path] = []

    def flush_current() -> None:
        nonlocal current_name, current_bus_info, current_nodes
        if current_name is None:
            return
        devices.append(
            V4L2Device(
                name=current_name,
                bus_info=current_bus_info,
                video_nodes=tuple(current_nodes),
            )
        )
        current_name = None
        current_bus_info = None
        current_nodes = []

    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue

        if raw_line.startswith("\t"):
            stripped = raw_line.strip()
            if stripped.startswith("/dev/video"):
                current_nodes.append(Path(stripped))
            continue

        flush_current()
        header = raw_line.rstrip(":")
        if " (" in header and header.endswith(")"):
            name, bus_info = header.rsplit(" (", 1)
            current_name = name
            current_bus_info = bus_info[:-1]
        else:
            current_name = header
            current_bus_info = None

    flush_current()
    return devices


def list_v4l2_devices(command: str = "v4l2-ctl") -> list[V4L2Device]:
    """Run `v4l2-ctl --list-devices` and parse the result."""

    executable = shutil.which(command)
    if executable is None:
        raise RuntimeError(f"Required command not found: {command}")

    result = subprocess.run(
        [executable, "--list-devices"],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_v4l2_device_listing(result.stdout)


def discover_video_nodes(directory: Path = Path("/dev")) -> list[Path]:
    """Discover raw `/dev/video*` nodes without external tools."""

    def sort_key(path: Path) -> tuple[int, str]:
        suffix = path.name.removeprefix("video")
        return (int(suffix), path.name) if suffix.isdigit() else (10**9, path.name)

    return sorted(
        (path for path in directory.glob("video*") if path.name.startswith("video")),
        key=sort_key,
    )


def discover_video_links(
    directory: Path = Path("/dev/v4l/by-id"),
) -> list[VideoNodeLink]:
    """Discover symbolic links that point at video nodes."""

    if not directory.exists():
        return []

    links: list[VideoNodeLink] = []
    for alias in sorted(directory.iterdir()):
        if not alias.is_symlink():
            continue
        links.append(
            VideoNodeLink(
                alias=alias,
                target=alias.resolve(),
            )
        )
    return links
