from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MOTOR_SRC = PROJECT_ROOT / "motor_fault_pca_project" / "src"
sys.path.append(str(MOTOR_SRC))

from realtime_features import visual_vibration_features_from_frames  # noqa: E402


def _moving_target_frames() -> tuple[list[np.ndarray], list[float]]:
    frames: list[np.ndarray] = []
    timestamps: list[float] = []
    for index in range(24):
        frame = np.zeros((80, 96), dtype=np.uint8)
        x = 30 + int(round(4 * math.sin(index * math.pi / 4)))
        y = 28
        frame[y : y + 18, x : x + 22] = 180
        frame[y + 4 : y + 14, x + 5 : x + 17] = 255
        frame[y + 8, x + 2 : x + 20] = 40
        frame[y + 2 : y + 16, x + 11] = 40
        frames.append(frame)
        timestamps.append(index * 0.05)
    return frames, timestamps


def _vibrating_object_frames() -> tuple[list[np.ndarray], list[float]]:
    frames: list[np.ndarray] = []
    timestamps: list[float] = []
    for index in range(32):
        frame = np.zeros((90, 120), dtype=np.uint8)
        frame[24:68, 36:88] = 95
        frame[30:62, 45:79] = 125
        shift = int(round(3 * math.sin(index * math.pi / 2)))
        frame[42:52, 58 + shift : 70 + shift] = 230
        frame[34:58, 40] = 180
        frame[34:58, 84] = 180
        frames.append(frame)
        timestamps.append(index * 0.04)
    return frames, timestamps


def test_visual_auto_roi_tracks_moving_target() -> None:
    frames, timestamps = _moving_target_frames()

    features = visual_vibration_features_from_frames(
        frames=frames,
        timestamps=timestamps,
        auto_roi=True,
        min_tracks=2,
        min_frequency=0.1,
    )

    assert features["vision_mask_source_code"] == 2.0
    assert features["tracked_points"] >= 2.0
    assert 20 <= features["roi_x"] <= 38
    assert 16 <= features["roi_w"] <= 48
    assert features["vision_mask_area_ratio"] < 0.25
    assert features["vision_dx_peak_to_peak"] > 0


def test_visual_features_accept_provided_mask() -> None:
    frames, timestamps = _moving_target_frames()
    mask = np.zeros_like(frames[0])
    mask[22:52, 24:62] = 255

    features = visual_vibration_features_from_frames(
        frames=frames,
        timestamps=timestamps,
        mask=mask,
        min_tracks=2,
        min_frequency=0.1,
    )

    assert features["vision_mask_source_code"] == 1.0
    assert features["roi_x"] == 24.0
    assert features["roi_y"] == 22.0
    assert features["roi_w"] == 38.0
    assert features["roi_h"] == 30.0


def test_visual_auto_object_expands_vibration_seed_to_object() -> None:
    frames, timestamps = _vibrating_object_frames()

    features = visual_vibration_features_from_frames(
        frames=frames,
        timestamps=timestamps,
        auto_object=True,
        min_tracks=2,
        min_frequency=0.1,
    )

    assert features["vision_mask_source_code"] == 3.0
    assert features["tracked_points"] >= 2.0
    assert features["roi_w"] >= 30.0
    assert features["roi_h"] >= 25.0
    assert features["vision_mask_area_ratio"] < 0.6
