"""Minimal CDC stream adapter for IMU capture.

The current test suite exercises only the synthetic capture path, but the live
capture service imports this module unconditionally. Keep the implementation
small and dependency-light so API imports succeed even when serial hardware or
`pyserial` is unavailable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from project_course.services.imu_protocol import IMUSamplePacket, parse_sample_packet


class IMUStreamTimeoutError(TimeoutError):
    """Raised when the CDC stream does not produce data in time."""


@dataclass(frozen=True)
class TimedIMUSample:
    """One parsed IMU sample paired with the local host timestamp."""

    packet: IMUSamplePacket
    host_time_s: float


class IMUCDCStream:
    """Small context-managed wrapper around an optional serial CDC device."""

    def __init__(self, *, port: str, baudrate: int, read_timeout_s: float) -> None:
        self.port = port
        self.baudrate = baudrate
        self.read_timeout_s = read_timeout_s
        self._serial = None

    def __enter__(self) -> "IMUCDCStream":
        try:
            import serial  # type: ignore[import-not-found]
        except ImportError as exc:
            raise OSError("pyserial is required for live IMU capture") from exc

        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.read_timeout_s,
        )
        return self

    def __exit__(self, *_: object) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def write_text(self, payload: str) -> None:
        if self._serial is None:
            raise RuntimeError("stream is not open")
        self._serial.write(payload.encode("ascii"))

    def read_handshake_line(self, *, timeout_s: float) -> str:
        if self._serial is None:
            raise RuntimeError("stream is not open")
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            raw = self._serial.readline()
            if raw:
                return raw.decode("utf-8", errors="replace").strip()
        raise IMUStreamTimeoutError("Timed out waiting for handshake")

    def read_sample_resync(
        self,
        *,
        frame_format: str,
        frame_size: int,
        timeout_s: float,
    ) -> TimedIMUSample:
        if self._serial is None:
            raise RuntimeError("stream is not open")
        self._serial.timeout = min(timeout_s, self.read_timeout_s)
        raw = self._serial.read(frame_size)
        if len(raw) != frame_size:
            raise IMUStreamTimeoutError("Timed out waiting for IMU frame")
        return TimedIMUSample(
            packet=parse_sample_packet(raw, frame_format=frame_format),
            host_time_s=time.time(),
        )
