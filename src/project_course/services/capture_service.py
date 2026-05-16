"""Task orchestration for camera + IMU capture sessions."""

from __future__ import annotations

import glob
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from project_course.api.config import settings
from project_course.camera.core import CameraConfig
from project_course.fusion.camera_features import extract_camera_features
from project_course.fusion.feature_vector_fusion import (
    build_fused_feature_vector,
    compute_display_fused_frequency,
)
from project_course.fusion.imu_features import extract_imu_features
from project_course.fusion.time_sync import (
    SyncFitResult,
    fit_clock_map,
    map_tick_to_host_time,
    unwrap_ticks,
)
from project_course.services.error_codes import DISK_SPACE_LOW, IMU_STREAM_TIMEOUT
from project_course.services.imu_protocol import (
    BINARY34_FRAME_SIZE,
    HandshakePacket,
    ProtocolError,
    parse_handshake_line,
    validate_handshake,
)
from project_course.services.imu_stream import (
    IMUCDCStream,
    IMUStreamTimeoutError,
    TimedIMUSample,
)


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
        """Run one capture/inference window pipeline and return windows + vectors."""

        mode = settings.imu_source_mode.strip().lower()
        if mode == "live":
            return self._run_live_pipeline(request, task_id=task_id)
        if mode == "synthetic":
            return self._run_synthetic_pipeline(request, task_id=task_id)
        if mode != "auto":
            raise RuntimeError(
                f"Unsupported imu_source_mode: {settings.imu_source_mode}"
            )
        if self._should_use_live_imu():
            try:
                return self._run_live_pipeline(request, task_id=task_id)
            except Exception:
                return self._run_synthetic_pipeline(request, task_id=task_id)
        return self._run_synthetic_pipeline(request, task_id=task_id)

    def _should_use_live_imu(self) -> bool:
        mode = settings.imu_source_mode.strip().lower()
        if mode == "live":
            return True
        if mode == "synthetic":
            return False
        if mode != "auto":
            raise RuntimeError(
                f"Unsupported imu_source_mode: {settings.imu_source_mode}"
            )
        return Path(settings.imu_serial_port).exists()

    def _run_synthetic_pipeline(
        self,
        request: CaptureRequest,
        *,
        task_id: str,
    ) -> tuple[list[dict[str, object]], list[list[float]]]:
        """Synthetic fallback pipeline used in tests and non-hardware environments."""

        window_count = settings.imu_capture_windows
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

    def _run_live_pipeline(
        self,
        request: CaptureRequest,
        *,
        task_id: str,
    ) -> tuple[list[dict[str, object]], list[list[float]]]:
        window_count = settings.imu_capture_windows
        imu_count = int(request.imu_sample_rate_hz * request.window_size_s)
        hop_count = max(1, int(request.imu_sample_rate_hz * request.window_hop_s))
        total_samples = imu_count + (window_count - 1) * hop_count
        frame_timeout_s = settings.imu_stream_timeout_ms / 1000.0

        try:
            samples, fit, sync_failed = self._collect_imu_samples(
                request=request,
                total_samples=total_samples,
                frame_timeout_s=frame_timeout_s,
            )
        except IMUStreamTimeoutError as exc:
            raise RuntimeError(
                f"{IMU_STREAM_TIMEOUT.code}: {IMU_STREAM_TIMEOUT.message}"
            ) from exc

        windows: list[dict[str, object]] = []
        vectors: list[list[float]] = []
        imu_ticks = unwrap_ticks([s.packet.t_imu_tick_us for s in samples])
        host_times = [s.host_time_s for s in samples]

        for idx in range(window_count):
            start = idx * hop_count
            end = start + imu_count
            win_samples = samples[start:end]

            imu_window = {
                "ax": np.asarray([row.packet.ax for row in win_samples], dtype=float),
                "ay": np.asarray([row.packet.ay for row in win_samples], dtype=float),
                "az": np.asarray([row.packet.az for row in win_samples], dtype=float),
                "gx": np.asarray([row.packet.gx for row in win_samples], dtype=float),
                "gy": np.asarray([row.packet.gy for row in win_samples], dtype=float),
                "gz": np.asarray([row.packet.gz for row in win_samples], dtype=float),
            }
            cam_count = int(420 * request.window_size_s)
            cam_t = np.linspace(0, request.window_size_s, cam_count, endpoint=False)
            base_freq = 20.0 + idx * 0.5
            dx = np.sin(2 * np.pi * base_freq * cam_t)
            dy = np.sin(2 * np.pi * (base_freq + 0.8) * cam_t)

            seq_gap_count = 0
            crc_bad_count = 0
            for off in range(1, len(win_samples)):
                prev = win_samples[off - 1].packet.imu_seq
                curr = win_samples[off].packet.imu_seq
                if curr != prev + 1:
                    seq_gap_count += 1
            for row in win_samples:
                if not row.packet.packet_crc_ok:
                    crc_bad_count += 1

            center_pos = start + imu_count // 2
            center_time = host_times[center_pos]
            if fit is not None and not sync_failed:
                center_time = map_tick_to_host_time(imu_ticks[center_pos], fit)

            imu_quality_flag = "ok"
            if seq_gap_count > 0 or crc_bad_count > 0:
                imu_quality_flag = "degraded"

            features: dict[str, object] = {
                "sample_id": task_id,
                "window_index": idx,
                "center_time_s": float(center_time),
                "imu_quality_flag": imu_quality_flag,
                "cam_quality_flag": "ok",
                "sync_fit_failed": sync_failed,
                "seq_gap_count": seq_gap_count,
                "crc_bad_count": crc_bad_count,
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
            features["_spectra"] = {
                "vision_dx": self._spectrum_payload(dx, 420.0),
                "vision_dy": self._spectrum_payload(dy, 420.0),
                "sensor_ax": self._spectrum_payload(
                    imu_window["ax"], request.imu_sample_rate_hz
                ),
                "sensor_ay": self._spectrum_payload(
                    imu_window["ay"], request.imu_sample_rate_hz
                ),
                "sensor_az": self._spectrum_payload(
                    imu_window["az"], request.imu_sample_rate_hz
                ),
                "sensor_gx": self._spectrum_payload(
                    imu_window["gx"], request.imu_sample_rate_hz
                ),
                "sensor_gy": self._spectrum_payload(
                    imu_window["gy"], request.imu_sample_rate_hz
                ),
                "sensor_gz": self._spectrum_payload(
                    imu_window["gz"], request.imu_sample_rate_hz
                ),
            }
            windows.append(features)

        return windows, vectors

    def _collect_imu_samples(
        self,
        *,
        request: CaptureRequest,
        total_samples: int,
        frame_timeout_s: float,
    ) -> tuple[list[TimedIMUSample], SyncFitResult | None, bool]:
        last_error: Exception | None = None
        for port in self._candidate_imu_ports():
            try:
                with IMUCDCStream(
                    port=port,
                    baudrate=settings.imu_serial_baudrate,
                    read_timeout_s=min(0.05, frame_timeout_s / 4.0),
                ) as stream:
                    frame_format = self._negotiate_handshake(stream, request)
                    samples: list[TimedIMUSample] = []
                    while len(samples) < total_samples:
                        sample = stream.read_sample_resync(
                            frame_format=frame_format,
                            frame_size=BINARY34_FRAME_SIZE,
                            timeout_s=frame_timeout_s,
                        )
                        samples.append(sample)
                break
            except Exception as exc:
                last_error = exc
                continue
        else:
            if isinstance(last_error, Exception):
                raise last_error
            raise IMUStreamTimeoutError("No candidate IMU CDC ports found")

        imu_ticks = unwrap_ticks([s.packet.t_imu_tick_us for s in samples])
        host_times = [s.host_time_s for s in samples]
        try:
            fit = fit_clock_map(imu_ticks, host_times)
            sync_failed = fit.r2 < settings.sync_fit_r2_threshold
        except ValueError:
            fit = None
            sync_failed = True
        return samples, fit, sync_failed

    def _negotiate_handshake(
        self,
        stream: IMUCDCStream,
        request: CaptureRequest,
    ) -> str:
        """Actively negotiate handshake with retry and ACK."""

        retry_count = max(1, int(settings.imu_handshake_retry_count))
        timeout_s = max(0.05, settings.imu_handshake_timeout_ms / 1000.0)

        for _ in range(retry_count):
            try:
                stream.write_text("HS_REQ\n")
                handshake_line = stream.read_handshake_line(timeout_s=timeout_s)
                handshake = parse_handshake_line(handshake_line)
                self.validate_handshake(handshake, request)
                stream.write_text("HS_ACK\n")
                return handshake.frame_format
            except (IMUStreamTimeoutError, ProtocolError):
                continue

        return "binary34"

    def _candidate_imu_ports(self) -> list[str]:
        ports = [settings.imu_serial_port]
        for path in sorted(glob.glob("/dev/ttyACM*")):
            if path not in ports:
                ports.append(path)
        return ports

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
