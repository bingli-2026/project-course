import numpy as np
import pytest

from project_course.api.live.real_pipeline import (
    FrameSample,
    _current_sync_metrics,
    _expand_roi,
    _latest_complete_window_index,
    _slice_time_window,
    _window_rate_hz,
)


def test_slice_time_window_keeps_only_in_range() -> None:
    samples = [
        FrameSample(timestamp_s=1.0, gray_frame=np.zeros((2, 2), dtype=np.uint8)),
        FrameSample(timestamp_s=1.2, gray_frame=np.zeros((2, 2), dtype=np.uint8)),
        FrameSample(timestamp_s=1.5, gray_frame=np.zeros((2, 2), dtype=np.uint8)),
    ]

    sliced = _slice_time_window(samples, 1.1, 1.3)

    assert [sample.timestamp_s for sample in sliced] == [1.2]


def test_window_rate_hz_uses_timestamp_spacing() -> None:
    timestamps = [10.0, 10.25, 10.5, 10.75]
    assert _window_rate_hz(timestamps) == 4.0


def test_expand_roi_adds_padding_and_clamps_to_frame() -> None:
    assert _expand_roi((10, 20, 30, 40), frame_width=100, frame_height=120) == (0, 0, 64, 84)
    assert _expand_roi(None, frame_width=100, frame_height=120) is None


def test_current_sync_metrics_reports_overlap_for_parallel_windows() -> None:
    metrics = _current_sync_metrics(
        visual_start=10.0,
        visual_end=10.5,
        imu_start=10.02,
        imu_end=10.48,
        requested_window_s=0.5,
        requested_imu_hz=400.0,
        payload={"analysis_fps": 390.0, "sensor_sample_rate_hz": 395.0},
    )

    assert metrics["offset_ms"] == 0.0
    assert metrics["aligned_ratio"] == pytest.approx(0.92)
    assert metrics["drift_ppm"] == pytest.approx(25000.0)


def test_latest_complete_window_index_skips_to_newest_ready_window() -> None:
    assert _latest_complete_window_index(
        started_at_s=10.0,
        window_size_s=0.5,
        window_hop_s=0.25,
        now_s=10.49,
    ) is None
    assert _latest_complete_window_index(
        started_at_s=10.0,
        window_size_s=0.5,
        window_hop_s=0.25,
        now_s=11.26,
    ) == 3
