from pathlib import Path

import pytest

from project_course.camera import (
    V4L2Device,
    VideoNodeLink,
    discover_video_links,
    discover_video_nodes,
    parse_v4l2_device_listing,
    validate_fourcc,
)


def test_validate_fourcc_accepts_none_and_four_char_values() -> None:
    validate_fourcc(None)
    validate_fourcc("YUYV")


def test_validate_fourcc_rejects_invalid_length() -> None:
    with pytest.raises(ValueError):
        validate_fourcc("YUY")


def test_parse_v4l2_device_listing_parses_multiple_devices() -> None:
    text = """
Integrated Camera: Integrated C (usb-0000:06:00.0-2):
\t/dev/video0
\t/dev/video1
\t/dev/media0

LRCP U3-JX02: LRCP U3-JX02 (usb-0000:07:00.4-2.4):
\t/dev/video2
\t/dev/video3
\t/dev/media1
""".strip()

    devices = parse_v4l2_device_listing(text)

    assert devices == [
        V4L2Device(
            name="Integrated Camera: Integrated C",
            bus_info="usb-0000:06:00.0-2",
            video_nodes=(Path("/dev/video0"), Path("/dev/video1")),
        ),
        V4L2Device(
            name="LRCP U3-JX02: LRCP U3-JX02",
            bus_info="usb-0000:07:00.4-2.4",
            video_nodes=(Path("/dev/video2"), Path("/dev/video3")),
        ),
    ]


def test_discover_video_nodes_sorts_numeric_suffixes(tmp_path: Path) -> None:
    for name in ("video10", "video2", "video0", "not-video"):
        (tmp_path / name).touch()

    nodes = discover_video_nodes(tmp_path)

    assert nodes == [
        tmp_path / "video0",
        tmp_path / "video2",
        tmp_path / "video10",
    ]


def test_discover_video_links_returns_symlink_targets(tmp_path: Path) -> None:
    target = tmp_path / "video2"
    target.touch()
    link = tmp_path / "camera-link"
    link.symlink_to(target)

    links = discover_video_links(tmp_path)

    assert links == [VideoNodeLink(alias=link, target=target)]
