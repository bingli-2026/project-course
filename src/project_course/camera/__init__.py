"""Reusable camera tools for the main project package."""

from .core import (
    CameraConfig,
    CaptureSummary,
    capture_properties,
    configure_capture,
    open_capture,
    probe_capture,
    save_frame,
    validate_fourcc,
)
from .v4l2 import (
    V4L2Device,
    VideoNodeLink,
    discover_video_links,
    discover_video_nodes,
    list_v4l2_devices,
    parse_v4l2_device_listing,
)

__all__ = [
    "CameraConfig",
    "CaptureSummary",
    "V4L2Device",
    "VideoNodeLink",
    "capture_properties",
    "configure_capture",
    "discover_video_links",
    "discover_video_nodes",
    "list_v4l2_devices",
    "open_capture",
    "parse_v4l2_device_listing",
    "probe_capture",
    "save_frame",
    "validate_fourcc",
]
