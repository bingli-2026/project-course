"""Task orchestration for camera + IMU capture sessions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from project_course.api.config import settings
from project_course.camera.core import CameraConfig
from project_course.fusion.camera_features import extract_camera_features
from project_course.fusion.feature_vector_fusion import (
    build_fused_feature_vector,
    compute_display_fused_frequency,
)
from project_course.fusion.imu_features import extract_imu_features
from project_course.services.error_codes import DISK_SPACE_LOW
from project_course.services.imu_protocol import HandshakePacket, validate_handshake


@dataclass(frozen=True)
class CaptureRequest:
    """User-facing capture request payload."""

    device_id: str
    camera_mode: str = "YUY2_160x140_420fps"
    imu_sample_rate_hz: int = settings.default_imu_sample_rate_hz
    window_size_s: float = settings.default_window_size_s
    window_hop_s: float = settings.default_window_hop_s
    roi_x: int | None = None
    roi_y: int | None = None
    roi_w: int | None = None
    roi_h: int | None = None


class CaptureService:
    """Capture orchestrator for US1 MVP.

    Uses synthetic signals to exercise the full data path before hardware stream
    integration in follow-up tasks.
    """

    def build_camera_config(self, request: CaptureRequest) -> CameraConfig:
        """Translate task request into camera config for the existing module."""

        return CameraConfig(
            device=0,
            backend="v4l2",
            width=settings.default_roi_w,
            height=settings.default_roi_h,
            fps=420.0,
            fourcc="YUYV",
        )

    def resolve_roi(self, request: CaptureRequest) -> tuple[int, int, int, int]:
        """Resolve ROI from payload or fall back to configured defaults."""

        return (
            request.roi_x if request.roi_x is not None else settings.default_roi_x,
            request.roi_y if request.roi_y is not None else settings.default_roi_y,
            request.roi_w if request.roi_w is not None else settings.default_roi_w,
            request.roi_h if request.roi_h is not None else settings.default_roi_h,
        )

    def validate_handshake(
        self,
        packet: HandshakePacket,
        request: CaptureRequest,
    ) -> None:
        """Validate incoming handshake against task-level sampling config."""

        validate_handshake(packet, expected_sample_rate_hz=request.imu_sample_rate_hz)

    def check_disk_guard(self, *, estimated_bytes: int, free_bytes: int) -> None:
        """Enforce startup disk safety ratio from config."""

        if free_bytes < int(estimated_bytes * settings.disk_guard_ratio):
            raise RuntimeError(f"{DISK_SPACE_LOW.code}: {DISK_SPACE_LOW.message}")

    def run_capture_pipeline(
        self,
        request: CaptureRequest,
        *,
        task_id: str,
    ) -> tuple[list[dict[str, object]], list[list[float]]]:
        """Run a synthetic window pipeline and return windows + fused vectors."""

        window_count = 8
        windows: list[dict[str, object]] = []
        vectors: list[list[float]] = []

        for idx in range(window_count):
            imu_count = int(request.imu_sample_rate_hz * request.window_size_s)
            cam_count = int(420 * request.window_size_s)
            imu_t = np.linspace(0, request.window_size_s, imu_count, endpoint=False)
            cam_t = np.linspace(0, request.window_size_s, cam_count, endpoint=False)
            base_freq = 20.0 + idx * 0.5

            imu_window = {
                "ax": np.sin(2 * np.pi * base_freq * imu_t),
                "ay": np.sin(2 * np.pi * (base_freq + 1.0) * imu_t),
                "az": np.sin(2 * np.pi * (base_freq + 2.0) * imu_t),
                "gx": np.sin(2 * np.pi * (base_freq + 0.2) * imu_t),
                "gy": np.sin(2 * np.pi * (base_freq + 1.2) * imu_t),
                "gz": np.sin(2 * np.pi * (base_freq + 2.2) * imu_t),
            }
            dx = np.sin(2 * np.pi * base_freq * cam_t)
            dy = np.sin(2 * np.pi * (base_freq + 0.8) * cam_t)

            center_time = (idx * request.window_hop_s) + request.window_size_s / 2
            features: dict[str, object] = {
                "sample_id": task_id,
                "window_index": idx,
                "center_time_s": center_time,
                "imu_quality_flag": "ok",
                "cam_quality_flag": "ok",
                "sync_fit_failed": False,
                "seq_gap_count": 0,
            }
            features.update(
                extract_imu_features(imu_window, request.imu_sample_rate_hz)
            )
            features.update(extract_camera_features(dx, dy, 420.0))

            numeric_features = {
                k: float(v)
                for k, v in features.items()
                if isinstance(v, (int, float))
            }
            fused_freq, fused_conf = compute_display_fused_frequency(numeric_features)
            features["fused_dominant_freq_hz"] = fused_freq
            features["fusion_confidence"] = fused_conf

            vector = build_fused_feature_vector(numeric_features)
            vectors.append(vector)

            sample_rate = request.imu_sample_rate_hz
            features["_spectra"] = {
                "vision_dx": self._spectrum_payload(dx, 420.0),
                "vision_dy": self._spectrum_payload(dy, 420.0),
                "sensor_ax": self._spectrum_payload(imu_window["ax"], sample_rate),
                "sensor_ay": self._spectrum_payload(imu_window["ay"], sample_rate),
                "sensor_az": self._spectrum_payload(imu_window["az"], sample_rate),
                "sensor_gx": self._spectrum_payload(imu_window["gx"], sample_rate),
                "sensor_gy": self._spectrum_payload(imu_window["gy"], sample_rate),
                "sensor_gz": self._spectrum_payload(imu_window["gz"], sample_rate),
            }
            windows.append(features)

        return windows, vectors

    @staticmethod
    def _spectrum_payload(
        signal: np.ndarray,
        sample_rate_hz: float,
    ) -> dict[str, list[float]]:
        freq = np.fft.rfftfreq(len(signal), d=1.0 / sample_rate_hz)
        power = np.abs(np.fft.rfft(signal)) ** 2
        return {
            "freq_hz": [float(v) for v in freq[:128]],
            "power": [float(v) for v in power[:128]],
        }
