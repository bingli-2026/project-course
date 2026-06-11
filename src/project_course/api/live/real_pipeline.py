"""Real hardware capture pipeline for the demo dashboard.

The earlier demo path captured one full camera window and then one full IMU
window sequentially. That made synchronization impossible and also pushed
camera acquisition work onto the critical path. This module keeps the public
live-buffer contract unchanged but moves capture to dedicated worker threads:

- camera worker: continuously reads frames into a ring buffer
- IMU worker: continuously polls the sensor into a ring buffer
- analysis loop: slices aligned windows by timestamp and publishes features
"""

from __future__ import annotations

import asyncio
import logging
import math
import sys
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, TypeVar

import numpy as np

from project_course.api.config import settings
from project_course.api.live import LIVE_STATE, finish_task, publish_window, record_sync_quality
from project_course.api.storage import db

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_MOTOR_SRC = _REPO_ROOT / "motor_fault_pca_project" / "src"
_MODEL_DIR = _REPO_ROOT / "motor_fault_pca_project" / "models"
_VISUAL_MODEL_PATH = _MODEL_DIR / "visual_pca_model.pkl"
_VIBRATION_MODEL_PATH = _MODEL_DIR / "vibration_pca_model.pkl"
if str(_MOTOR_SRC) not in sys.path:
    sys.path.append(str(_MOTOR_SRC))

from realtime_features import (  # type: ignore[import-not-found]  # noqa: E402
    _init_ms6dsv,
    _read_ms6dsv_burst_sample,
    vibration_features_from_i2c_samples,
    visual_vibration_features_from_frames,
)


_DETECTOR_CACHE: dict[str, Any] = {
    "attempted": False,
    "visual": None,
    "vibration": None,
}

_SampleT = TypeVar("_SampleT")


@dataclass(slots=True)
class FrameSample:
    timestamp_s: float
    gray_frame: np.ndarray


@dataclass(slots=True)
class ImuSample:
    timestamp_s: float
    accel: tuple[int, int, int]
    gyro: tuple[int, int, int] | None = None


@dataclass
class _TaskWindowState:
    task_id: str
    started_at_s: float
    next_window_end_s: float
    window_index: int = 0
    last_auto_roi: tuple[int, int, int, int] | None = None
    sync_history: dict[str, deque[float]] = field(
        default_factory=lambda: {
            "offset_ms": deque(maxlen=64),
            "drift_ppm": deque(maxlen=64),
            "aligned_ratio": deque(maxlen=64),
        }
    )


class _CaptureBuffers:
    def __init__(self) -> None:
        buffer_seconds = max(2.0, float(settings.real_capture_buffer_s))
        self._camera_buffer: deque[FrameSample] = deque(
            maxlen=max(64, int(math.ceil(settings.real_camera_fps * buffer_seconds * 1.5)))
        )
        self._imu_buffer: deque[ImuSample] = deque(
            maxlen=max(128, int(math.ceil(settings.imu_sample_rate_hz * buffer_seconds * 1.5)))
        )
        self._lock = threading.RLock()
        self._desired_imu_hz = max(1, settings.imu_sample_rate_hz)
        self._camera_error: str | None = None
        self._imu_error: str | None = None

    def reset_for_task(self, imu_hz: int) -> None:
        with self._lock:
            self._camera_buffer.clear()
            self._imu_buffer.clear()
            self._desired_imu_hz = max(1, int(imu_hz))
            self._camera_error = None
            self._imu_error = None

    def append_camera(self, sample: FrameSample) -> None:
        with self._lock:
            self._camera_buffer.append(sample)
            self._camera_error = None

    def append_imu(self, sample: ImuSample) -> None:
        with self._lock:
            self._imu_buffer.append(sample)
            self._imu_error = None

    def set_camera_error(self, message: str) -> None:
        with self._lock:
            self._camera_error = message

    def set_imu_error(self, message: str) -> None:
        with self._lock:
            self._imu_error = message

    def snapshot_errors(self) -> tuple[str | None, str | None]:
        with self._lock:
            return self._camera_error, self._imu_error

    def desired_imu_hz(self) -> int:
        with self._lock:
            return self._desired_imu_hz

    def camera_window(self, start_s: float, end_s: float) -> list[FrameSample]:
        with self._lock:
            return _slice_time_window(self._camera_buffer, start_s, end_s)

    def imu_window(self, start_s: float, end_s: float) -> list[ImuSample]:
        with self._lock:
            return _slice_time_window(self._imu_buffer, start_s, end_s)


class _CaptureWorkers:
    def __init__(self) -> None:
        self.buffers = _CaptureBuffers()
        self._stop_event = threading.Event()
        self._camera_thread: threading.Thread | None = None
        self._imu_thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._camera_thread = threading.Thread(target=self._camera_worker, name="real-camera-capture", daemon=True)
        self._imu_thread = threading.Thread(target=self._imu_worker, name="real-imu-capture", daemon=True)
        self._camera_thread.start()
        self._imu_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for thread in [self._camera_thread, self._imu_thread]:
            if thread is not None:
                thread.join(timeout=2.0)

    def _camera_worker(self) -> None:
        import cv2

        while not self._stop_event.is_set():
            cap = cv2.VideoCapture(settings.real_camera_index)
            if not cap.isOpened():
                self.buffers.set_camera_error(f"cannot open camera index {settings.real_camera_index}")
                logger.warning("real camera worker cannot open camera index %s", settings.real_camera_index)
                self._stop_event.wait(0.5)
                continue

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.real_camera_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.real_camera_height)
            cap.set(cv2.CAP_PROP_FPS, settings.real_camera_fps)
            if settings.real_camera_fourcc:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*settings.real_camera_fourcc))

            try:
                while not self._stop_event.is_set():
                    ok, frame = cap.read()
                    if not ok:
                        self.buffers.set_camera_error("camera read failed")
                        self._stop_event.wait(0.002)
                        continue
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    self.buffers.append_camera(FrameSample(timestamp_s=time.time(), gray_frame=gray))
            except Exception as exc:  # pragma: no cover - device-specific runtime path
                logger.exception("real camera worker crashed")
                self.buffers.set_camera_error(str(exc))
                self._stop_event.wait(0.2)
            finally:
                cap.release()

    def _imu_worker(self) -> None:
        from smbus2 import SMBus

        while not self._stop_event.is_set():
            try:
                with SMBus(settings.real_imu_bus_id) as bus:
                    _init_ms6dsv(bus, settings.real_imu_address)
                    next_deadline = time.perf_counter()

                    while not self._stop_event.is_set():
                        gyro, accel = _read_ms6dsv_burst_sample(bus, settings.real_imu_address)
                        include_gyro = settings.real_include_gyro
                        self.buffers.append_imu(
                            ImuSample(
                                timestamp_s=time.time(),
                                accel=accel,
                                gyro=gyro if include_gyro else None,
                            )
                        )

                        target_hz = self.buffers.desired_imu_hz()
                        period_s = 1.0 / target_hz if target_hz > 0 else 0.0
                        if period_s <= 0:
                            continue
                        next_deadline += period_s
                        sleep_s = next_deadline - time.perf_counter()
                        if sleep_s > 0:
                            self._stop_event.wait(sleep_s)
                        elif sleep_s < -(period_s * 2.0):
                            next_deadline = time.perf_counter()
            except Exception as exc:  # pragma: no cover - device-specific runtime path
                logger.exception("real IMU worker crashed")
                self.buffers.set_imu_error(str(exc))
                self._stop_event.wait(0.5)


_CAPTURE_WORKERS = _CaptureWorkers()


def get_real_model_version() -> str:
    has_visual = _VISUAL_MODEL_PATH.exists()
    has_vibration = _VIBRATION_MODEL_PATH.exists()
    if has_visual and has_vibration:
        return "edge-live-pca-v0"
    if has_visual or has_vibration:
        return "edge-live-partial-pca-v0"
    return "edge-live-heuristic-v0"


def _task_config(task_id: str) -> dict[str, Any]:
    row = db.get_task(task_id)
    if row is None:
        raise RuntimeError(f"task {task_id} no longer exists in SQLite")
    return dict(row)


def _window_payload(
    task_id: str,
    window_index: int,
    *,
    task_started_at_s: float,
    window_start_s: float,
    window_end_s: float,
    last_auto_roi: tuple[int, int, int, int] | None,
) -> tuple[dict[str, Any], dict[str, float | None], tuple[int, int, int, int] | None]:
    row = _task_config(task_id)
    requested_window_s = float(row["window_size_s"])
    manual_roi = _roi_from_row(row)
    camera_error, imu_error = _CAPTURE_WORKERS.buffers.snapshot_errors()

    payload: dict[str, Any] = {
        "sample_id": f"{task_id}-w{window_index:04d}",
        "window_index": window_index,
        "center_time_s": max(0.0, ((window_start_s + window_end_s) / 2.0) - task_started_at_s),
        "modality": "fused",
    }

    visual_start: float | None = None
    visual_end: float | None = None
    imu_start: float | None = None
    imu_end: float | None = None
    next_auto_roi = last_auto_roi
    cam_ok = False
    imu_ok = False

    try:
        visual_features = _visual_features_for_window(
            window_start_s=window_start_s,
            window_end_s=window_end_s,
            manual_roi=manual_roi,
            previous_auto_roi=last_auto_roi,
        )
        visual_start = visual_features.pop("_visual_start_time", None)
        visual_end = visual_features.pop("_visual_end_time", None)
        payload.update(visual_features)
        next_auto_roi = _payload_roi(visual_features) if manual_roi is None else manual_roi
        cam_ok = True
    except Exception as exc:  # pragma: no cover - exercised on device
        camera_error = str(exc)
        logger.exception("real camera analysis failed for %s", task_id)

    try:
        vibration_features = _vibration_features_for_window(
            window_start_s=window_start_s,
            window_end_s=window_end_s,
        )
        imu_start = vibration_features.pop("_imu_start_time", None)
        imu_end = vibration_features.pop("_imu_end_time", None)
        payload.update(vibration_features)
        imu_ok = True
    except Exception as exc:  # pragma: no cover - exercised on device
        imu_error = str(exc)
        logger.exception("real IMU analysis failed for %s", task_id)

    if not cam_ok and not imu_ok:
        details = [part for part in [camera_error, imu_error] if part]
        message = "camera and imu capture both failed"
        if details:
            message = f"{message}: {'; '.join(details)}"
        raise RuntimeError(message)

    payload["cam_quality_flag"] = "ok" if cam_ok else "capture_failed"
    payload["imu_quality_flag"] = "ok" if imu_ok else "capture_failed"
    payload["sync_fit_failed"] = not (cam_ok and imu_ok)
    payload["seq_gap_count"] = 0
    if camera_error:
        payload["camera_error"] = camera_error
    if imu_error:
        payload["imu_error"] = imu_error

    sync_metrics = _current_sync_metrics(
        visual_start=visual_start,
        visual_end=visual_end,
        imu_start=imu_start,
        imu_end=imu_end,
        requested_window_s=requested_window_s,
        requested_imu_hz=float(row["imu_sample_rate_hz"]),
        payload=payload,
    )
    payload.update(
        {
            "sync_offset_ms": sync_metrics["offset_ms"],
            "sync_drift_ppm_window": sync_metrics["drift_ppm"],
            "sync_overlap_ratio": sync_metrics["aligned_ratio"],
        }
    )

    fused_frequency_hz, fusion_confidence = _fused_frequency(payload)
    if fused_frequency_hz is not None:
        payload["fused_dominant_freq_hz"] = fused_frequency_hz
        payload["fusion_confidence"] = fusion_confidence

    predicted_state, prediction_confidence = _predict_state(payload)
    payload["predicted_state"] = predicted_state
    payload["prediction_confidence"] = prediction_confidence
    payload["prediction_source"] = get_real_model_version()

    return payload, sync_metrics, next_auto_roi


def _visual_features_for_window(
    *,
    window_start_s: float,
    window_end_s: float,
    manual_roi: tuple[int, int, int, int] | None,
    previous_auto_roi: tuple[int, int, int, int] | None,
) -> dict[str, Any]:
    frame_samples = _CAPTURE_WORKERS.buffers.camera_window(window_start_s, window_end_s)
    if len(frame_samples) < 8:
        raise ValueError(f"not enough camera frames in window: {len(frame_samples)}")

    timestamps = [sample.timestamp_s for sample in frame_samples]
    frames = [sample.gray_frame for sample in frame_samples]
    search_roi = manual_roi or _expand_roi(
        previous_auto_roi,
        frame_width=frames[0].shape[1],
        frame_height=frames[0].shape[0],
    )
    processed_frames = _prepare_visual_frames(frames)
    features = visual_vibration_features_from_frames(
        frames=processed_frames,
        timestamps=timestamps,
        roi=manual_roi,
        search_roi=search_roi,
        max_corners=settings.real_visual_max_corners,
        min_frequency=settings.real_visual_min_frequency_hz,
        max_frequency=settings.real_visual_max_frequency_hz,
        auto_object=manual_roi is None,
    )
    features["_visual_start_time"] = timestamps[0]
    features["_visual_end_time"] = timestamps[-1]
    return features


def _vibration_features_for_window(
    *,
    window_start_s: float,
    window_end_s: float,
) -> dict[str, Any]:
    imu_samples = _CAPTURE_WORKERS.buffers.imu_window(window_start_s, window_end_s)
    if len(imu_samples) < 8:
        raise ValueError(f"not enough imu samples in window: {len(imu_samples)}")

    timestamps = [sample.timestamp_s for sample in imu_samples]
    accel_samples = [sample.accel for sample in imu_samples]
    gyro_samples = [sample.gyro for sample in imu_samples if sample.gyro is not None]
    elapsed_s = max(1e-9, timestamps[-1] - timestamps[0])
    effective_rate_hz = _window_rate_hz(timestamps)
    features = vibration_features_from_i2c_samples(
        accel_samples=accel_samples,
        gyro_samples=gyro_samples if gyro_samples else None,
        sample_rate_hz=effective_rate_hz if effective_rate_hz > 0 else 1.0,
        window_seconds=elapsed_s,
    )
    features["_imu_start_time"] = timestamps[0]
    features["_imu_end_time"] = timestamps[-1]
    return features


def _prepare_visual_frames(frames: list[np.ndarray]) -> list[np.ndarray]:
    if not settings.real_visual_use_clahe:
        return [frame.copy() for frame in frames]

    import cv2

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return [clahe.apply(frame) for frame in frames]


def _roi_from_row(row: dict[str, Any]) -> tuple[int, int, int, int] | None:
    values = [row.get("roi_x"), row.get("roi_y"), row.get("roi_w"), row.get("roi_h")]
    if any(value is None for value in values):
        return None
    return tuple(int(value) for value in values)  # type: ignore[return-value]


def _payload_roi(payload: dict[str, Any]) -> tuple[int, int, int, int] | None:
    values = [payload.get("roi_x"), payload.get("roi_y"), payload.get("roi_w"), payload.get("roi_h")]
    if not all(isinstance(value, (int, float)) for value in values):
        return None
    x, y, w, h = [int(float(value)) for value in values]
    if w <= 0 or h <= 0:
        return None
    return (x, y, w, h)


def _expand_roi(
    roi: tuple[int, int, int, int] | None,
    *,
    frame_width: int,
    frame_height: int,
) -> tuple[int, int, int, int] | None:
    if roi is None:
        return None
    x, y, w, h = roi
    padding = max(24, int(max(w, h) * 0.5))
    x0 = max(0, x - padding)
    y0 = max(0, y - padding)
    x1 = min(frame_width, x + w + padding)
    y1 = min(frame_height, y + h + padding)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1 - x0, y1 - y0


def _slice_time_window(buffer: deque[_SampleT], start_s: float, end_s: float) -> list[_SampleT]:
    return [sample for sample in buffer if start_s <= getattr(sample, "timestamp_s") <= end_s]


def _window_rate_hz(timestamps: list[float]) -> float:
    if len(timestamps) < 2:
        return 0.0
    duration = timestamps[-1] - timestamps[0]
    if duration <= 0:
        return 0.0
    return max(0.0, (len(timestamps) - 1) / duration)


def _latest_complete_window_index(
    *,
    started_at_s: float,
    window_size_s: float,
    window_hop_s: float,
    now_s: float,
) -> int | None:
    ready_s = now_s - started_at_s - window_size_s
    if ready_s < 0:
        return None
    if window_hop_s <= 0:
        return 0
    return max(0, int(math.floor(ready_s / window_hop_s)))


def _dominant_axis_peak(payload: dict[str, Any], *, axes: tuple[str, ...]) -> float | None:
    best_peak: float | None = None
    best_power = float("-inf")
    for axis in axes:
        peak = payload.get(f"{axis}_peak_hz")
        power = payload.get(f"{axis}_peak_power")
        if not isinstance(peak, (int, float)) or not isinstance(power, (int, float)):
            continue
        if float(power) > best_power:
            best_power = float(power)
            best_peak = float(peak)
    return best_peak


def _peak_share(payload: dict[str, Any], axis: str) -> float:
    peak_power = payload.get(f"{axis}_peak_power")
    band_power = payload.get(f"{axis}_band_power")
    if not isinstance(peak_power, (int, float)) or not isinstance(band_power, (int, float)) or band_power <= 0:
        return 0.0
    return max(0.0, min(1.0, float(peak_power) / float(band_power)))


def _visual_reference_peak(payload: dict[str, Any]) -> float | None:
    consensus = payload.get("vision_consensus_peak_hz")
    if isinstance(consensus, (int, float)) and float(consensus) > 0:
        return float(consensus)
    return _dominant_axis_peak(payload, axes=("vision_dx", "vision_dy"))


def _sensor_reference_peak(payload: dict[str, Any]) -> float | None:
    magnitude = payload.get("sensor_accel_magnitude_peak_hz")
    if isinstance(magnitude, (int, float)) and float(magnitude) > 0:
        return float(magnitude)
    return _dominant_axis_peak(payload, axes=("sensor_ax", "sensor_ay", "sensor_az"))


def _visual_quality(payload: dict[str, Any]) -> float:
    tracked = payload.get("tracked_points")
    support = payload.get("vision_consensus_support")
    support_ratio = 0.0
    if isinstance(tracked, (int, float)) and tracked > 0 and isinstance(support, (int, float)):
        support_ratio = max(0.0, min(1.0, float(support) / float(tracked)))
    peak_share = max(_peak_share(payload, "vision_dx"), _peak_share(payload, "vision_dy"))
    return max(0.0, min(1.0, 0.65 * support_ratio + 0.35 * peak_share))


def _sensor_quality(payload: dict[str, Any]) -> float:
    peak_share = max(
        _peak_share(payload, "sensor_accel_magnitude"),
        _peak_share(payload, "sensor_ax"),
        _peak_share(payload, "sensor_ay"),
        _peak_share(payload, "sensor_az"),
    )
    mean_abs = payload.get("sensor_accel_magnitude_mean_abs")
    peak_to_peak = payload.get("sensor_accel_magnitude_peak_to_peak")
    variability = 0.0
    if isinstance(mean_abs, (int, float)) and mean_abs and isinstance(peak_to_peak, (int, float)):
        variability = max(0.0, min(1.0, float(peak_to_peak) / max(float(mean_abs) * 0.02, 1.0)))
    return max(0.0, min(1.0, 0.7 * peak_share + 0.3 * variability))


def _fused_frequency(payload: dict[str, Any]) -> tuple[float | None, float]:
    vision_peak = _visual_reference_peak(payload)
    sensor_peak = _sensor_reference_peak(payload)
    vision_quality = _visual_quality(payload)
    sensor_quality = _sensor_quality(payload)

    if vision_peak is None and sensor_peak is None:
        return None, 0.0
    if sensor_peak is None:
        return vision_peak, max(0.15, min(0.75, 0.25 + 0.5 * vision_quality))
    if vision_peak is None:
        return sensor_peak, max(0.15, min(0.9, 0.35 + 0.55 * sensor_quality))

    delta = abs(sensor_peak - vision_peak)
    tolerance = max(3.0, 0.2 * max(sensor_peak, vision_peak))
    if delta <= tolerance:
        total_weight = max(0.1, vision_quality) + max(0.1, sensor_quality)
        fused = (vision_peak * max(0.1, vision_quality) + sensor_peak * max(0.1, sensor_quality)) / total_weight
        agreement = 1.0 - (delta / tolerance)
        confidence = max(0.15, min(1.0, 0.35 + 0.35 * agreement + 0.3 * (vision_quality + sensor_quality) / 2.0))
        return round(float(fused), 6), float(confidence)

    if sensor_quality >= vision_quality:
        confidence = max(0.15, min(0.9, 0.25 + 0.55 * sensor_quality))
        return sensor_peak, float(confidence)
    confidence = max(0.15, min(0.75, 0.2 + 0.45 * vision_quality))
    return vision_peak, float(confidence)


def _ensure_detectors_loaded() -> None:
    if _DETECTOR_CACHE["attempted"]:
        return
    _DETECTOR_CACHE["attempted"] = True
    try:
        from pca_detector import PCAFaultDetector  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - import availability is environment-specific
        logger.warning("PCA detector import unavailable; falling back to heuristic live predictions: %s", exc)
        return

    for branch, path in [("visual", _VISUAL_MODEL_PATH), ("vibration", _VIBRATION_MODEL_PATH)]:
        if not path.exists():
            continue
        try:
            _DETECTOR_CACHE[branch] = PCAFaultDetector.load(path)
            logger.info("loaded %s PCA model from %s", branch, path)
        except Exception as exc:  # pragma: no cover - model files are device-specific
            logger.warning("failed to load %s PCA model from %s: %s", branch, path, exc)


def _predict_state(payload: dict[str, Any]) -> tuple[str, float]:
    _ensure_detectors_loaded()
    branch_predictions: list[tuple[str, str, float]] = []

    visual_detector = _DETECTOR_CACHE.get("visual")
    if visual_detector is not None:
        result = _predict_branch(payload, visual_detector, "visual")
        if result is not None:
            branch_predictions.append(result)
            payload["visual_branch_state"] = result[1]
            payload["visual_branch_confidence"] = result[2]

    vibration_detector = _DETECTOR_CACHE.get("vibration")
    if vibration_detector is not None:
        result = _predict_branch(payload, vibration_detector, "vibration")
        if result is not None:
            branch_predictions.append(result)
            payload["vibration_branch_state"] = result[1]
            payload["vibration_branch_confidence"] = result[2]

    if branch_predictions:
        return _combine_branch_predictions(branch_predictions)

    return _heuristic_prediction(payload)


def _predict_branch(payload: dict[str, Any], detector: Any, branch: str) -> tuple[str, str, float] | None:
    feature_columns = getattr(detector, "feature_columns_", None)
    if not feature_columns:
        return None

    row: dict[str, float] = {}
    for column in feature_columns:
        value = payload.get(column)
        if not isinstance(value, (int, float)) or math.isnan(float(value)):
            return None
        row[column] = float(value)

    try:
        import pandas as pd
    except Exception as exc:  # pragma: no cover - pandas availability is environment-specific
        logger.warning("pandas unavailable for %s branch prediction: %s", branch, exc)
        return None

    output = detector.predict(pd.DataFrame([row], columns=list(feature_columns)))
    score = float(output.scores[0])
    threshold = float(output.threshold)
    prediction = str(output.predictions[0])
    margin = abs(score - threshold) / max(abs(threshold), 1e-9)
    confidence = max(0.0, min(1.0, 0.5 + 0.5 * min(1.0, margin)))

    payload[f"{branch}_branch_score"] = score
    payload[f"{branch}_branch_threshold"] = threshold
    return branch, prediction, confidence


def _combine_branch_predictions(branch_predictions: list[tuple[str, str, float]]) -> tuple[str, float]:
    fault_conf = max((confidence for _branch, prediction, confidence in branch_predictions if prediction == "fault"), default=0.0)
    normal_conf = max((confidence for _branch, prediction, confidence in branch_predictions if prediction == "normal"), default=0.0)

    if fault_conf == 0.0 and normal_conf == 0.0:
        return "unknown", 0.0
    if fault_conf > normal_conf:
        return "fault", max(0.1, min(1.0, fault_conf))
    if normal_conf > fault_conf:
        return "normal", max(0.1, min(1.0, normal_conf))
    return "normal", max(0.1, min(1.0, (fault_conf + normal_conf) / 2.0))


def _heuristic_prediction(payload: dict[str, Any]) -> tuple[str, float]:
    if payload.get("cam_quality_flag") != "ok" and payload.get("imu_quality_flag") != "ok":
        return "unknown", 0.0

    vision_quality = _visual_quality(payload)
    sensor_quality = _sensor_quality(payload)
    combined_quality = max(vision_quality, sensor_quality)
    if combined_quality < 0.1:
        return "unknown", 0.2

    sensor_variability = 0.0
    mean_abs = payload.get("sensor_accel_magnitude_mean_abs")
    peak_to_peak = payload.get("sensor_accel_magnitude_peak_to_peak")
    if isinstance(mean_abs, (int, float)) and mean_abs and isinstance(peak_to_peak, (int, float)):
        sensor_variability = max(0.0, min(1.0, float(peak_to_peak) / max(float(mean_abs) * 0.01, 1.0)))

    anomaly_score = (
        0.45 * max(
            _peak_share(payload, "sensor_accel_magnitude"),
            _peak_share(payload, "sensor_ax"),
            _peak_share(payload, "sensor_ay"),
            _peak_share(payload, "sensor_az"),
        )
        + 0.3 * sensor_variability
        + 0.25 * vision_quality
    )
    threshold = 0.42
    confidence = max(0.15, min(0.95, 0.5 + abs(anomaly_score - threshold)))
    return ("fault", confidence) if anomaly_score >= threshold else ("normal", confidence)


def _current_sync_metrics(
    *,
    visual_start: float | None,
    visual_end: float | None,
    imu_start: float | None,
    imu_end: float | None,
    requested_window_s: float,
    requested_imu_hz: float,
    payload: dict[str, Any],
) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {
        "offset_ms": None,
        "drift_ppm": None,
        "aligned_ratio": None,
    }
    if visual_start is None or visual_end is None or imu_start is None or imu_end is None:
        return metrics

    visual_center = (visual_start + visual_end) / 2.0
    imu_center = (imu_start + imu_end) / 2.0
    overlap_s = max(0.0, min(visual_end, imu_end) - max(visual_start, imu_start))
    nominal_window = max(1e-9, requested_window_s)
    metrics["offset_ms"] = abs(visual_center - imu_center) * 1000.0
    metrics["aligned_ratio"] = max(0.0, min(1.0, overlap_s / nominal_window))

    drift_candidates: list[float] = []
    analysis_fps = payload.get("analysis_fps")
    if isinstance(analysis_fps, (int, float)) and settings.real_camera_fps > 0:
        drift_candidates.append(abs(float(analysis_fps) - settings.real_camera_fps) / settings.real_camera_fps * 1_000_000.0)
    imu_rate = payload.get("sensor_sample_rate_hz")
    if isinstance(imu_rate, (int, float)) and requested_imu_hz > 0:
        drift_candidates.append(abs(float(imu_rate) - requested_imu_hz) / requested_imu_hz * 1_000_000.0)
    if drift_candidates:
        metrics["drift_ppm"] = max(drift_candidates)
    return metrics


def _rolling_sync_summary(
    history: dict[str, deque[float]],
    current: dict[str, float | None],
) -> dict[str, float | None]:
    for source_key, history_key in [
        ("offset_ms", "offset_ms"),
        ("drift_ppm", "drift_ppm"),
        ("aligned_ratio", "aligned_ratio"),
    ]:
        value = current.get(source_key)
        if isinstance(value, (int, float)):
            history[history_key].append(float(value))

    return {
        "offset_ms_p95": _percentile95(history["offset_ms"]),
        "drift_ppm": _percentile95(history["drift_ppm"]),
        "aligned_window_ratio": _mean_or_none(history["aligned_ratio"]),
    }


def _percentile95(values: deque[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return float(ordered[index])


def _mean_or_none(values: deque[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


async def _real_pipeline_loop() -> None:
    task_state: _TaskWindowState | None = None

    while True:
        active = LIVE_STATE.active_task
        if active is None:
            task_state = None
            await asyncio.sleep(0.2)
            continue

        if task_state is None or task_state.task_id != active.task_id:
            row = _task_config(active.task_id)
            task_started_at_s = time.time()
            task_state = _TaskWindowState(
                task_id=active.task_id,
                started_at_s=task_started_at_s,
                next_window_end_s=task_started_at_s + float(row["window_size_s"]),
            )
            _CAPTURE_WORKERS.buffers.reset_for_task(int(row["imu_sample_rate_hz"]))
            await asyncio.sleep(float(settings.real_analysis_poll_s))
            continue

        now_s = time.time()
        if now_s < task_state.next_window_end_s:
            await asyncio.sleep(min(float(settings.real_analysis_poll_s), task_state.next_window_end_s - now_s))
            continue

        row = _task_config(task_state.task_id)
        window_size_s = float(row["window_size_s"])
        window_hop_s = float(row["window_hop_s"])
        latest_complete_index = _latest_complete_window_index(
            started_at_s=task_state.started_at_s,
            window_size_s=window_size_s,
            window_hop_s=window_hop_s,
            now_s=now_s,
        )
        if latest_complete_index is None:
            await asyncio.sleep(float(settings.real_analysis_poll_s))
            continue
        if latest_complete_index > task_state.window_index:
            skipped = latest_complete_index - task_state.window_index
            logger.warning(
                "real pipeline lagged behind task %s; skipping %d stale window(s)",
                task_state.task_id,
                skipped,
            )
            task_state.window_index = latest_complete_index
            task_state.next_window_end_s = (
                task_state.started_at_s + window_size_s + latest_complete_index * window_hop_s
            )
        window_end_s = task_state.next_window_end_s
        window_start_s = window_end_s - window_size_s

        try:
            payload, sync_metrics, next_auto_roi = await asyncio.to_thread(
                _window_payload,
                task_state.task_id,
                task_state.window_index,
                task_started_at_s=task_state.started_at_s,
                window_start_s=window_start_s,
                window_end_s=window_end_s,
                last_auto_roi=task_state.last_auto_roi,
            )
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise
        except Exception as exc:  # pragma: no cover - exercised on device
            logger.exception("real pipeline failed for %s", task_state.task_id)
            finish_task(status="failed", error_message=str(exc))
            task_state = None
            await asyncio.sleep(0.2)
            continue

        if LIVE_STATE.active_task is None or LIVE_STATE.active_task.task_id != task_state.task_id:
            await asyncio.sleep(0)
            continue

        publish_window(payload)
        sync_summary = _rolling_sync_summary(task_state.sync_history, sync_metrics)
        record_sync_quality(
            offset_ms_p95=sync_summary["offset_ms_p95"],
            drift_ppm=sync_summary["drift_ppm"],
            aligned_window_ratio=sync_summary["aligned_window_ratio"],
        )
        task_state.window_index += 1
        task_state.next_window_end_s += window_hop_s
        task_state.last_auto_roi = next_auto_roi


@asynccontextmanager
async def real_pipeline_lifespan() -> AsyncIterator[None]:
    if not settings.real_pipeline_enabled:
        yield
        return

    _CAPTURE_WORKERS.start()
    task = asyncio.create_task(_real_pipeline_loop(), name="real-live-pipeline")
    logger.info("real live pipeline started")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        _CAPTURE_WORKERS.stop()
        logger.info("real live pipeline stopped")
