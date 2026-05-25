"""Runtime feature extraction for camera and vibration windows."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


NUMBER_PATTERN = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")

MS6DSV_I2C_BUS = 7
MS6DSV_I2C_ADDR = 0x6A
MS6DSV_WHO_AM_I_EXPECT = 0x70

REG_WHO_AM_I = 0x0F
REG_CTRL1 = 0x10
REG_CTRL2 = 0x11
REG_CTRL3 = 0x12
REG_CTRL6 = 0x15
REG_CTRL8 = 0x17
REG_OUTX_L_G = 0x22
REG_OUTX_L_A = 0x28

ODR_60HZ = 0x05
FS_G_2000DPS = 0x04
FS_XL_2G = 0x00


@dataclass
class WindowRecord:
    features: dict[str, float]
    start_time: float
    end_time: float


def parse_numeric_line(line: str) -> list[float]:
    """Parse serial lines such as '0.1,0.2,0.3' or 'ax=0.1 ay=0.2 az=0.3'."""
    return [float(value) for value in NUMBER_PATTERN.findall(line)]


def append_feature_row(csv_path: str | Path, row: dict) -> None:
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([row])
    df.to_csv(csv_path, mode="a", index=False, header=not csv_path.exists())


def align_feature_dict(features: dict[str, float], feature_columns: Iterable[str]) -> pd.DataFrame:
    missing = [name for name in feature_columns if name not in features]
    if missing:
        raise ValueError(
            "Live feature names do not match the trained PCA model. "
            f"Missing columns: {missing}. "
            "Use the same feature extractor for training and runtime detection."
        )
    return pd.DataFrame([{name: features[name] for name in feature_columns}])


def visual_motion_window_from_camera(
    camera_index: int,
    window_seconds: float,
    width: int = 160,
    height: int = 140,
    fps: int = 420,
    fourcc: str = "YUY2",
    resize_width: int | None = 320,
) -> WindowRecord:
    import cv2

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {camera_index}.")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if fourcc:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))

    start_time = time.time()
    prev_gray = None
    frame_features: list[dict[str, float]] = []

    try:
        while time.time() - start_time < window_seconds:
            ok, frame = cap.read()
            if not ok:
                continue

            if resize_width and frame.shape[1] > resize_width:
                scale = resize_width / frame.shape[1]
                new_size = (resize_width, int(frame.shape[0] * scale))
                frame = cv2.resize(frame, new_size)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                frame_features.append(_visual_pair_features(prev_gray, gray))
            prev_gray = gray
    finally:
        cap.release()

    end_time = time.time()
    return WindowRecord(
        features=_aggregate_frame_features(frame_features, prefix="visual"),
        start_time=start_time,
        end_time=end_time,
    )


def visual_vibration_window_from_camera(
    camera_index: int,
    window_seconds: float,
    width: int = 160,
    height: int = 140,
    fps: int = 420,
    fourcc: str = "YUY2",
    roi: tuple[int, int, int, int] | None = None,
    max_corners: int = 80,
    min_tracks: int = 5,
    min_frequency: float = 1.0,
    max_frequency: float | None = None,
    use_clahe: bool = True,
    auto_roi: bool = False,
    auto_object: bool = False,
) -> WindowRecord:
    """Extract vibration-focused visual spectrum features from a live camera.

    This path is less sensitive to lighting than frame differencing because it
    tracks feature-point displacement inside a fixed ROI and analyzes dx/dy
    frequency content.
    """
    import cv2

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {camera_index}.")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if fourcc:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))

    start_time = time.time()
    frames: list[np.ndarray] = []
    timestamps: list[float] = []
    appearance_frame: np.ndarray | None = None
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)) if use_clahe else None

    try:
        while time.time() - start_time < window_seconds:
            ok, frame = cap.read()
            if not ok:
                continue
            appearance_frame = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if clahe is not None:
                gray = clahe.apply(gray)
            frames.append(gray)
            timestamps.append(time.time())
    finally:
        cap.release()

    end_time = time.time()
    features = visual_vibration_features_from_frames(
        frames=frames,
        timestamps=timestamps,
        roi=roi,
        max_corners=max_corners,
        min_tracks=min_tracks,
        min_frequency=min_frequency,
        max_frequency=max_frequency,
        auto_roi=auto_roi,
        auto_object=auto_object,
        appearance_frame=appearance_frame,
    )
    return WindowRecord(features=features, start_time=start_time, end_time=end_time)


def visual_vibration_features_from_frames(
    frames: list[np.ndarray],
    timestamps: list[float],
    roi: tuple[int, int, int, int] | None = None,
    mask: np.ndarray | None = None,
    max_corners: int = 80,
    min_tracks: int = 5,
    min_frequency: float = 1.0,
    max_frequency: float | None = None,
    auto_roi: bool = False,
    auto_object: bool = False,
    appearance_frame: np.ndarray | None = None,
) -> dict[str, float]:
    import cv2

    if len(frames) < 8:
        raise ValueError("Not enough camera frames captured for visual vibration analysis.")

    height, width = frames[0].shape
    if mask is not None and mask.shape != frames[0].shape:
        raise ValueError(
            f"Mask shape {mask.shape} does not match frame shape {frames[0].shape}."
        )

    search_roi = roi
    if search_roi is None:
        search_roi = (0, 0, width, height)
    _validate_roi(width, height, search_roi)

    mask_source = "manual_roi"
    if mask is not None:
        feature_mask = _prepare_feature_mask(mask, search_roi)
        x, y, w, h = _bbox_from_mask(feature_mask)
        mask_source = "provided_mask"
    elif auto_object:
        feature_mask, (x, y, w, h) = _vibrating_object_mask_from_frames(
            frames=frames,
            timestamps=timestamps,
            search_roi=search_roi,
            appearance_frame=appearance_frame,
        )
        mask_source = "auto_vibrating_object"
    elif auto_roi:
        feature_mask, (x, y, w, h) = _motion_mask_from_frames(
            frames=frames,
            search_roi=search_roi,
        )
        mask_source = "auto_motion"
    else:
        x, y, w, h = _validate_roi(width, height, search_roi)
        feature_mask = np.zeros_like(frames[0], dtype=np.uint8)
        feature_mask[y : y + h, x : x + w] = 255

    corners = cv2.goodFeaturesToTrack(
        frames[0],
        maxCorners=max_corners,
        qualityLevel=0.01,
        minDistance=4,
        blockSize=7,
        mask=feature_mask,
    )
    if corners is None or len(corners) < min_tracks:
        raise ValueError("Not enough stable visual corners in ROI. Adjust ROI or lighting.")

    initial = corners.reshape(-1, 2)
    current = corners
    valid = np.ones(len(initial), dtype=bool)
    dx_trace = [np.zeros(len(initial), dtype=float)]
    dy_trace = [np.zeros(len(initial), dtype=float)]

    lk_params = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    prev = frames[0]
    for frame in frames[1:]:
        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev, frame, current, None, **lk_params)
        if next_pts is None or status is None:
            break
        status = status.reshape(-1).astype(bool)
        valid &= status
        displacement = next_pts.reshape(-1, 2) - initial
        dx_trace.append(displacement[:, 0])
        dy_trace.append(displacement[:, 1])
        current = next_pts
        prev = frame

    dx_array = np.asarray(dx_trace, dtype=float)[:, valid]
    dy_array = np.asarray(dy_trace, dtype=float)[:, valid]
    if dx_array.shape[1] < min_tracks:
        raise ValueError("Too few valid visual tracks remained in ROI.")

    dx = _detrend(np.median(dx_array, axis=1))
    dy = _detrend(np.median(dy_array, axis=1))
    analysis_fps = _effective_fps(timestamps[: len(dx)])

    features: dict[str, float] = {
        "roi_x": float(x),
        "roi_y": float(y),
        "roi_w": float(w),
        "roi_h": float(h),
        "analysis_fps": float(analysis_fps),
        "vision_mask_source_code": float(_mask_source_code(mask_source)),
        "vision_mask_area_ratio": float(np.mean(feature_mask > 0)),
        "tracked_points": float(dx_array.shape[1]),
        "vision_dx_std": float(np.std(dx)),
        "vision_dy_std": float(np.std(dy)),
        "vision_dx_peak_to_peak": float(np.max(dx) - np.min(dx)),
        "vision_dy_peak_to_peak": float(np.max(dy) - np.min(dy)),
    }
    features.update(_spectrum_features("vision_dx", dx, analysis_fps, min_frequency, max_frequency))
    features.update(_spectrum_features("vision_dy", dy, analysis_fps, min_frequency, max_frequency))
    return features


def vibration_window_from_serial(
    port: str,
    baudrate: int,
    window_seconds: float,
    sample_rate_hz: int = 1680,
    min_values_per_line: int = 3,
    axis_start_index: int = 0,
) -> WindowRecord:
    import serial

    start_time = time.time()
    samples: list[list[float]] = []

    with serial.Serial(port=port, baudrate=baudrate, timeout=0.2) as ser:
        while time.time() - start_time < window_seconds:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore")
            values = parse_numeric_line(line)
            if len(values) >= axis_start_index + min_values_per_line:
                samples.append(values[axis_start_index : axis_start_index + 3])

    end_time = time.time()
    return WindowRecord(
        features=vibration_features_from_samples(
            samples,
            sample_rate_hz=sample_rate_hz,
            window_seconds=window_seconds,
        ),
        start_time=start_time,
        end_time=end_time,
    )


def vibration_window_from_i2c(
    bus_id: int = MS6DSV_I2C_BUS,
    address: int = MS6DSV_I2C_ADDR,
    window_seconds: float = 2.0,
    sample_rate_hz: int = 60,
    include_gyro: bool = False,
) -> WindowRecord:
    from smbus2 import SMBus

    start_time = time.time()
    accel_samples: list[tuple[int, int, int]] = []
    gyro_samples: list[tuple[int, int, int]] = []

    with SMBus(bus_id) as bus:
        _init_ms6dsv(bus, address)
        delay = 1.0 / sample_rate_hz if sample_rate_hz > 0 else 0.02

        while time.time() - start_time < window_seconds:
            accel_samples.append(_read_vec3(bus, address, REG_OUTX_L_A))
            if include_gyro:
                gyro_samples.append(_read_vec3(bus, address, REG_OUTX_L_G))
            time.sleep(delay)

    end_time = time.time()
    return WindowRecord(
        features=vibration_features_from_i2c_samples(
            accel_samples=accel_samples,
            gyro_samples=gyro_samples if include_gyro else None,
            sample_rate_hz=sample_rate_hz,
            window_seconds=window_seconds,
        ),
        start_time=start_time,
        end_time=end_time,
    )


def vibration_features_from_samples(
    samples: list[list[float]],
    sample_rate_hz: int = 1680,
    window_seconds: float | None = None,
) -> dict[str, float]:
    if not samples:
        raise ValueError("No vibration samples captured in the current window.")

    min_len = min(len(row) for row in samples)
    data = np.asarray([row[:min_len] for row in samples], dtype=float)
    # ADXL345 provides three-axis acceleration. Runtime PCA uses only ax/ay/az.
    axis_names = ["ax", "ay", "az"]
    axis_count = min(data.shape[1], len(axis_names))
    data = data[:, :axis_count]

    features: dict[str, float] = {
        "sensor_sample_rate_hz": float(sample_rate_hz),
        "sensor_window_duration_s": float(window_seconds) if window_seconds else float(data.shape[0] / sample_rate_hz),
        "imu_sample_count": float(data.shape[0]),
    }

    for axis_index, axis_name in enumerate(axis_names[:axis_count]):
        _add_signal_features(features, f"sensor_{axis_name}", data[:, axis_index], sample_rate_hz)

    if axis_count >= 3:
        magnitude = np.sqrt(np.sum(data[:, :3] ** 2, axis=1))
        _add_signal_features(features, "sensor_accel_magnitude", magnitude, sample_rate_hz)

    return features


def vibration_features_from_i2c_samples(
    accel_samples: list[tuple[int, int, int]],
    gyro_samples: list[tuple[int, int, int]] | None = None,
    sample_rate_hz: int = 60,
    window_seconds: float | None = None,
) -> dict[str, float]:
    if not accel_samples:
        raise ValueError("No I2C acceleration samples captured in the current window.")

    accel = np.asarray(accel_samples, dtype=float)
    features: dict[str, float] = {
        "sensor_sample_rate_hz": float(sample_rate_hz),
        "sensor_window_duration_s": float(window_seconds) if window_seconds else float(len(accel) / sample_rate_hz),
        "imu_sample_count": float(len(accel)),
    }

    for axis_index, axis_name in enumerate(["ax", "ay", "az"]):
        _add_signal_features(features, f"sensor_{axis_name}", accel[:, axis_index], sample_rate_hz)

    magnitude = np.sqrt(np.sum(accel**2, axis=1))
    _add_signal_features(features, "sensor_accel_magnitude", magnitude, sample_rate_hz)

    if gyro_samples:
        gyro = np.asarray(gyro_samples, dtype=float)
        count = min(len(accel), len(gyro))
        gyro = gyro[:count]
        for axis_index, axis_name in enumerate(["gx", "gy", "gz"]):
            _add_signal_features(features, f"sensor_{axis_name}", gyro[:, axis_index], sample_rate_hz)

    return features


def _visual_pair_features(prev_gray: np.ndarray, gray: np.ndarray) -> dict[str, float]:
    import cv2

    diff = cv2.absdiff(prev_gray, gray).astype(float) / 255.0
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray,
        gray,
        None,
        pyr_scale=0.5,
        levels=2,
        winsize=15,
        iterations=2,
        poly_n=5,
        poly_sigma=1.2,
        flags=0,
    )
    flow_mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)

    return {
        "diff_mean": float(np.mean(diff)),
        "diff_std": float(np.std(diff)),
        "diff_max": float(np.max(diff)),
        "diff_active_ratio": float(np.mean(diff > 0.08)),
        "flow_mean": float(np.mean(flow_mag)),
        "flow_std": float(np.std(flow_mag)),
        "flow_max": float(np.max(flow_mag)),
        "flow_p95": float(np.percentile(flow_mag, 95)),
        "flow_active_ratio": float(np.mean(flow_mag > 1.0)),
    }


def _aggregate_frame_features(
    frame_features: list[dict[str, float]],
    prefix: str,
) -> dict[str, float]:
    if not frame_features:
        raise ValueError("No valid camera frame pairs captured in the current window.")

    df = pd.DataFrame(frame_features)
    features: dict[str, float] = {
        f"{prefix}_frame_pair_count": float(len(frame_features)),
    }
    for column in df.columns:
        values = df[column].to_numpy(dtype=float)
        features[f"{prefix}_{column}_mean"] = float(np.mean(values))
        features[f"{prefix}_{column}_std"] = float(np.std(values))
        features[f"{prefix}_{column}_max"] = float(np.max(values))
    return features


def _prepare_feature_mask(
    mask: np.ndarray,
    search_roi: tuple[int, int, int, int],
) -> np.ndarray:
    height, width = mask.shape
    x, y, w, h = _validate_roi(width, height, search_roi)
    feature_mask = np.zeros((height, width), dtype=np.uint8)
    feature_mask[mask > 0] = 255

    roi_limiter = np.zeros_like(feature_mask)
    roi_limiter[y : y + h, x : x + w] = 255
    feature_mask &= roi_limiter

    if not np.any(feature_mask):
        raise ValueError("Feature mask is empty inside the selected ROI.")
    return feature_mask


def _motion_mask_from_frames(
    frames: list[np.ndarray],
    search_roi: tuple[int, int, int, int],
    *,
    min_area_ratio: float = 0.005,
    max_area_ratio: float = 0.6,
    motion_percentile: float = 90.0,
    padding: int = 4,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    import cv2

    height, width = frames[0].shape
    x, y, w, h = _validate_roi(width, height, search_roi)
    motion = np.zeros((height, width), dtype=np.uint8)
    prev = _as_uint8_gray(frames[0])

    for frame in frames[1:]:
        current = _as_uint8_gray(frame)
        motion = np.maximum(motion, cv2.absdiff(prev, current))
        prev = current

    limited_motion = np.zeros_like(motion)
    limited_motion[y : y + h, x : x + w] = motion[y : y + h, x : x + w]
    if int(limited_motion.max()) == 0:
        raise ValueError("Auto ROI failed: no foreground motion found.")

    blurred = cv2.GaussianBlur(limited_motion, (5, 5), 0)
    roi_motion = blurred[y : y + h, x : x + w]
    otsu_threshold, _ = cv2.threshold(
        blurred,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    threshold = max(float(otsu_threshold), float(np.percentile(roi_motion, motion_percentile)))
    binary = np.where(blurred >= threshold, 255, 0).astype(np.uint8)
    if not np.any(binary):
        threshold = float(np.percentile(roi_motion, 98.0))
        binary = np.where(blurred >= threshold, 255, 0).astype(np.uint8)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    binary = cv2.dilate(binary, kernel, iterations=1)

    contours, _ = cv2.findContours(
        binary,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    min_area = max(4.0, float(w * h) * min_area_ratio)
    contours = [c for c in contours if cv2.contourArea(c) >= min_area]
    if not contours:
        raise ValueError("Auto ROI failed: foreground area is too small.")

    largest = max(contours, key=cv2.contourArea)
    bx, by, bw, bh = cv2.boundingRect(largest)
    if (bw * bh) / float(w * h) > max_area_ratio:
        threshold = float(np.percentile(roi_motion, 98.0))
        binary = np.where(blurred >= threshold, 255, 0).astype(np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        contours, _ = cv2.findContours(
            binary,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        contours = [c for c in contours if cv2.contourArea(c) >= min_area]
        if not contours:
            raise ValueError("Auto ROI failed: foreground area is too diffuse.")
        bx, by, bw, bh = cv2.boundingRect(max(contours, key=cv2.contourArea))

    px, py, pw, ph = _pad_bbox(bx, by, bw, bh, width, height, padding)

    feature_mask = np.zeros_like(motion)
    feature_mask[py : py + ph, px : px + pw] = 255
    feature_mask = _prepare_feature_mask(feature_mask, search_roi)
    return feature_mask, _bbox_from_mask(feature_mask)


def _vibrating_object_mask_from_frames(
    frames: list[np.ndarray],
    timestamps: list[float],
    search_roi: tuple[int, int, int, int],
    *,
    appearance_frame: np.ndarray | None = None,
    max_seed_corners: int = 450,
    min_seed_points: int = 4,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    import cv2

    if len(frames) < 12:
        raise ValueError("Auto object failed: at least 12 frames are required.")

    height, width = frames[0].shape
    x, y, w, h = _validate_roi(width, height, search_roi)
    roi_mask = np.zeros((height, width), dtype=np.uint8)
    roi_mask[y : y + h, x : x + w] = 255

    first = _as_uint8_gray(frames[0])
    corners = cv2.goodFeaturesToTrack(
        first,
        maxCorners=max_seed_corners,
        qualityLevel=0.004,
        minDistance=4,
        blockSize=5,
        mask=roi_mask,
    )
    if corners is None or len(corners) < min_seed_points:
        raise ValueError("Auto object failed: not enough feature points in ROI.")

    initial, x_tracks, y_tracks = _track_sparse_points(frames, corners)
    if x_tracks.shape[1] < min_seed_points:
        raise ValueError("Auto object failed: too few valid tracked points.")

    fps = _effective_fps(timestamps[: x_tracks.shape[0]])
    scores = _vibration_scores(x_tracks, y_tracks, fps)
    selected = _select_vibration_seed_points(scores, min_seed_points)
    seed_points = initial[selected]
    seed_mask = _seed_mask_from_points(seed_points, (height, width), radius=9)
    seed_mask = _largest_seed_component(seed_mask, seed_points, scores[selected])

    if not np.any(seed_mask):
        raise ValueError("Auto object failed: no vibration seed cluster found.")

    return _grow_object_mask_from_seed(
        frame=appearance_frame if appearance_frame is not None else first,
        search_roi=search_roi,
        seed_mask=seed_mask,
    )


def _track_sparse_points(
    frames: list[np.ndarray],
    corners: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import cv2

    initial = corners.reshape(-1, 2)
    current = corners
    valid = np.ones(len(initial), dtype=bool)
    tracks_x = [initial[:, 0].copy()]
    tracks_y = [initial[:, 1].copy()]
    prev = _as_uint8_gray(frames[0])
    lk_params = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    for frame in frames[1:]:
        current_frame = _as_uint8_gray(frame)
        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            prev,
            current_frame,
            current,
            None,
            **lk_params,
        )
        if next_pts is None or status is None:
            break
        valid &= status.reshape(-1).astype(bool)
        flat = next_pts.reshape(-1, 2)
        tracks_x.append(flat[:, 0].copy())
        tracks_y.append(flat[:, 1].copy())
        current = next_pts
        prev = current_frame

    return (
        initial[valid],
        np.asarray(tracks_x, dtype=float)[:, valid],
        np.asarray(tracks_y, dtype=float)[:, valid],
    )


def _vibration_scores(
    x_tracks: np.ndarray,
    y_tracks: np.ndarray,
    fps: float,
) -> np.ndarray:
    scores: list[float] = []
    for index in range(x_tracks.shape[1]):
        dx = _detrend(x_tracks[:, index] - x_tracks[0, index])
        dy = _detrend(y_tracks[:, index] - y_tracks[0, index])
        motion = np.sqrt(dx * dx + dy * dy)
        if len(motion) < 8 or fps <= 0:
            scores.append(float(np.std(motion)))
            continue

        window = np.hanning(len(motion))
        freqs = np.fft.rfftfreq(len(motion), d=1.0 / fps)
        power = np.abs(np.fft.rfft((motion - motion.mean()) * window)) ** 2
        high = (freqs >= 2.0) & (freqs <= min(0.45 * fps, 25.0))
        low = (freqs > 0.05) & (freqs < 2.0)
        high_power = float(power[high].sum())
        low_power = float(power[low].sum())
        scores.append(high_power / (low_power + 1e-6) * float(np.std(motion)))
    return np.asarray(scores, dtype=float)


def _select_vibration_seed_points(
    scores: np.ndarray,
    min_seed_points: int,
) -> np.ndarray:
    if not np.any(np.isfinite(scores)) or float(scores.max()) <= 0:
        raise ValueError("Auto object failed: no vibration-like point motion found.")

    threshold = max(
        float(np.percentile(scores, 85)),
        float(scores.mean() + 0.35 * scores.std()),
    )
    selected = scores >= threshold
    if int(selected.sum()) < min_seed_points:
        selected = scores >= float(np.percentile(scores, 75))
    if int(selected.sum()) < min_seed_points:
        raise ValueError("Auto object failed: too few vibration seed points.")
    return selected


def _seed_mask_from_points(
    points: np.ndarray,
    shape: tuple[int, int],
    radius: int,
) -> np.ndarray:
    import cv2

    height, width = shape
    seed_mask = np.zeros((height, width), dtype=np.uint8)
    for point in points:
        px, py = int(round(point[0])), int(round(point[1]))
        if 0 <= px < width and 0 <= py < height:
            cv2.circle(seed_mask, (px, py), radius, 255, -1)
    return seed_mask


def _largest_seed_component(
    seed_mask: np.ndarray,
    seed_points: np.ndarray,
    seed_scores: np.ndarray,
) -> np.ndarray:
    import cv2

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    merged = cv2.morphologyEx(seed_mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    num, labels, _stats, _centroids = cv2.connectedComponentsWithStats(merged, 8)
    if num <= 1:
        return merged

    best_label = 0
    best_score = -1.0
    for label in range(1, num):
        score = 0.0
        count = 0
        for point, point_score in zip(seed_points, seed_scores):
            px, py = int(round(point[0])), int(round(point[1]))
            if 0 <= py < labels.shape[0] and 0 <= px < labels.shape[1]:
                if labels[py, px] == label:
                    score += float(point_score)
                    count += 1
        if count:
            score = score / float(count**0.5)
        if score > best_score:
            best_score = score
            best_label = label
    return np.where(labels == best_label, 255, 0).astype(np.uint8)


def _grow_object_mask_from_seed(
    frame: np.ndarray,
    search_roi: tuple[int, int, int, int],
    seed_mask: np.ndarray,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    import cv2

    gray_frame = _as_uint8_gray(frame)
    height, width = gray_frame.shape
    x, y, w, h = _validate_roi(width, height, search_roi)
    seed_bbox = _bbox_from_mask(seed_mask)
    sx, sy, sw, sh = seed_bbox
    center_x = sx + sw // 2
    center_y = sy + sh // 2
    growth_w = min(max(64, sw * 7), max(64, int(width * 0.65)))
    growth_h = min(max(64, sh * 7), max(64, int(height * 0.75)))
    gx0 = max(x, center_x - growth_w // 2)
    gy0 = max(y, center_y - growth_h // 2)
    gx1 = min(x + w, center_x + growth_w // 2)
    gy1 = min(y + h, center_y + growth_h // 2)
    if gx1 <= gx0 or gy1 <= gy0:
        raise ValueError("Auto object failed: invalid object growth region.")

    grabcut_mask = np.full((height, width), cv2.GC_BGD, dtype=np.uint8)
    grabcut_mask[gy0:gy1, gx0:gx1] = cv2.GC_PR_BGD
    dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    probable_fg = cv2.dilate(seed_mask, dilate_kernel, iterations=1)
    grabcut_mask[probable_fg > 0] = cv2.GC_PR_FGD
    grabcut_mask[seed_mask > 0] = cv2.GC_FGD

    bgr = _as_bgr_frame(frame)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(
            bgr,
            grabcut_mask,
            None,
            bgd_model,
            fgd_model,
            5,
            cv2.GC_INIT_WITH_MASK,
        )
        object_mask = np.where(
            (grabcut_mask == cv2.GC_FGD) | (grabcut_mask == cv2.GC_PR_FGD),
            255,
            0,
        ).astype(np.uint8)
    except cv2.error:
        object_mask = probable_fg.astype(np.uint8)

    roi_limiter = np.zeros_like(object_mask)
    roi_limiter[y : y + h, x : x + w] = 255
    object_mask &= roi_limiter
    object_mask = _component_touching_seed(object_mask, seed_mask)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    object_mask = cv2.morphologyEx(object_mask, cv2.MORPH_CLOSE, close_kernel, 2)
    object_mask = cv2.dilate(object_mask, close_kernel, iterations=1)
    object_mask = _prepare_feature_mask(object_mask, search_roi)
    return object_mask, _bbox_from_mask(object_mask)


def _component_touching_seed(object_mask: np.ndarray, seed_mask: np.ndarray) -> np.ndarray:
    import cv2

    num, labels, stats, _centroids = cv2.connectedComponentsWithStats(object_mask, 8)
    best_label = 0
    best_score = -1
    for label in range(1, num):
        component = labels == label
        seed_overlap = int(np.count_nonzero(component & (seed_mask > 0)))
        area = int(stats[label, cv2.CC_STAT_AREA])
        score = seed_overlap * 1000 + area
        if seed_overlap > 0 and score > best_score:
            best_score = score
            best_label = label
    if best_label == 0:
        return object_mask
    return np.where(labels == best_label, 255, 0).astype(np.uint8)


def _as_uint8_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3:
        import cv2

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if frame.dtype == np.uint8:
        return frame
    clipped = np.clip(frame, 0, 255)
    return clipped.astype(np.uint8)


def _as_bgr_frame(frame: np.ndarray) -> np.ndarray:
    import cv2

    if frame.ndim == 2:
        gray = _as_uint8_gray(frame)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if frame.dtype == np.uint8:
        return frame
    clipped = np.clip(frame, 0, 255)
    return clipped.astype(np.uint8)


def _bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int]:
    import cv2

    points = cv2.findNonZero(mask)
    if points is None:
        raise ValueError("Feature mask is empty.")
    return tuple(int(value) for value in cv2.boundingRect(points))


def _pad_bbox(
    x: int,
    y: int,
    w: int,
    h: int,
    frame_width: int,
    frame_height: int,
    padding: int,
) -> tuple[int, int, int, int]:
    x0 = max(0, x - padding)
    y0 = max(0, y - padding)
    x1 = min(frame_width, x + w + padding)
    y1 = min(frame_height, y + h + padding)
    return x0, y0, x1 - x0, y1 - y0


def _mask_source_code(mask_source: str) -> int:
    return {
        "manual_roi": 0,
        "provided_mask": 1,
        "auto_motion": 2,
        "auto_vibrating_object": 3,
    }[mask_source]


def _validate_roi(
    frame_width: int,
    frame_height: int,
    roi: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    x, y, w, h = roi
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > frame_width or y + h > frame_height:
        raise ValueError(f"ROI {roi} is outside frame bounds {(frame_width, frame_height)}.")
    return x, y, w, h


def _effective_fps(timestamps: list[float]) -> float:
    if len(timestamps) < 2:
        return 1.0
    duration = timestamps[-1] - timestamps[0]
    if duration <= 0:
        return 1.0
    return (len(timestamps) - 1) / duration


def _detrend(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return values - np.mean(values)
    x = np.arange(len(values), dtype=float)
    slope, intercept = np.polyfit(x, values, 1)
    return values - (slope * x + intercept)


def _spectrum_features(
    prefix: str,
    values: np.ndarray,
    sample_rate_hz: float,
    min_frequency: float,
    max_frequency: float | None,
) -> dict[str, float]:
    centered = np.asarray(values, dtype=float) - np.mean(values)
    if len(centered) < 4 or sample_rate_hz <= 0:
        return _empty_spectrum_features(prefix)

    window = np.hanning(len(centered))
    freqs = np.fft.rfftfreq(len(centered), d=1.0 / sample_rate_hz)
    power = np.abs(np.fft.rfft(centered * window)) ** 2
    valid = freqs >= min_frequency
    if max_frequency is not None:
        valid &= freqs <= max_frequency
    if not np.any(valid):
        return _empty_spectrum_features(prefix)

    freqs = freqs[valid]
    power = power[valid]
    total_power = float(np.sum(power))
    if total_power <= 0:
        return _empty_spectrum_features(prefix)

    peak_index = int(np.argmax(power))
    probability = power / total_power
    return {
        f"{prefix}_peak_hz": float(freqs[peak_index]),
        f"{prefix}_peak_power": float(power[peak_index]),
        f"{prefix}_band_power": total_power,
        f"{prefix}_spectral_centroid_hz": float(np.sum(freqs * power) / total_power),
        f"{prefix}_spectral_entropy": float(-np.sum(probability * np.log2(probability + 1e-12))),
    }


def _empty_spectrum_features(prefix: str) -> dict[str, float]:
    return {
        f"{prefix}_peak_hz": 0.0,
        f"{prefix}_peak_power": 0.0,
        f"{prefix}_band_power": 0.0,
        f"{prefix}_spectral_centroid_hz": 0.0,
        f"{prefix}_spectral_entropy": 0.0,
    }


def _add_signal_features(
    features: dict[str, float],
    prefix: str,
    values: np.ndarray,
    sample_rate_hz: int,
) -> None:
    values = np.asarray(values, dtype=float)
    centered = values - np.mean(values)
    std = float(np.std(values))
    rms = float(np.sqrt(np.mean(values**2)))

    features[f"{prefix}_mean"] = float(np.mean(values))
    features[f"{prefix}_std"] = std
    features[f"{prefix}_rms"] = rms
    features[f"{prefix}_min"] = float(np.min(values))
    features[f"{prefix}_max"] = float(np.max(values))
    features[f"{prefix}_peak_to_peak"] = float(np.max(values) - np.min(values))
    features[f"{prefix}_mean_abs"] = float(np.mean(np.abs(values)))
    features[f"{prefix}_crest_factor"] = float(np.max(np.abs(values)) / rms) if rms > 0 else 0.0
    if std > 0:
        normalized = centered / std
        features[f"{prefix}_skew"] = float(np.mean(normalized**3))
        features[f"{prefix}_kurtosis"] = float(np.mean(normalized**4))
    else:
        features[f"{prefix}_skew"] = 0.0
        features[f"{prefix}_kurtosis"] = 0.0

    if len(values) >= 4 and sample_rate_hz > 0:
        freqs = np.fft.rfftfreq(len(centered), d=1.0 / sample_rate_hz)
        power = np.abs(np.fft.rfft(centered)) ** 2
        if len(power) > 1:
            freqs = freqs[1:]
            power = power[1:]
        total_power = float(np.sum(power))
        if total_power > 0:
            peak_index = int(np.argmax(power))
            probability = power / total_power
            features[f"{prefix}_peak_hz"] = float(freqs[peak_index])
            features[f"{prefix}_peak_power"] = float(power[peak_index])
            features[f"{prefix}_band_power"] = total_power
            features[f"{prefix}_spectral_centroid_hz"] = float(np.sum(freqs * power) / total_power)
            features[f"{prefix}_spectral_entropy"] = float(-np.sum(probability * np.log2(probability + 1e-12)))
        else:
            features[f"{prefix}_peak_hz"] = 0.0
            features[f"{prefix}_peak_power"] = 0.0
            features[f"{prefix}_band_power"] = 0.0
            features[f"{prefix}_spectral_centroid_hz"] = 0.0
            features[f"{prefix}_spectral_entropy"] = 0.0


def _init_ms6dsv(bus, address: int) -> None:
    who = bus.read_byte_data(address, REG_WHO_AM_I)
    if who != MS6DSV_WHO_AM_I_EXPECT:
        raise RuntimeError(
            f"Unexpected WHO_AM_I=0x{who:02X}; expected 0x{MS6DSV_WHO_AM_I_EXPECT:02X}."
        )

    # CTRL3: BDU=1(bit6), IF_INC=1(bit2)
    _update_bits(bus, address, REG_CTRL3, 0x44, 0x44)
    _update_bits(bus, address, REG_CTRL1, 0x0F, ODR_60HZ)
    _update_bits(bus, address, REG_CTRL2, 0x0F, ODR_60HZ)
    _update_bits(bus, address, REG_CTRL6, 0x0F, FS_G_2000DPS)
    _update_bits(bus, address, REG_CTRL8, 0x03, FS_XL_2G)


def _update_bits(bus, address: int, reg: int, mask: int, value: int) -> None:
    current = bus.read_byte_data(address, reg)
    updated = (current & ~mask) | (value & mask)
    bus.write_byte_data(address, reg, updated)


def _read_vec3(bus, address: int, base_reg: int) -> tuple[int, int, int]:
    data = bus.read_i2c_block_data(address, base_reg, 6)
    return (
        _to_i16(data[0], data[1]),
        _to_i16(data[2], data[3]),
        _to_i16(data[4], data[5]),
    )


def _to_i16(lo: int, hi: int) -> int:
    value = (hi << 8) | lo
    return value - 65536 if value & 0x8000 else value
