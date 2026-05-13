"""STM32 CDC protocol parsing and validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HandshakePacket:
    """Handshake metadata emitted as the first packet in a stream."""

    protocol_version: int
    imu_sample_rate_hz: int
    axis_order: str
    tick_hz: int
    frame_format: str


@dataclass(frozen=True)
class IMUSamplePacket:
    """A parsed 6-axis sample packet."""

    imu_seq: int
    t_imu_tick_us: int
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    packet_crc_ok: bool


class ProtocolError(ValueError):
    """Raised when a packet cannot be parsed or validated."""


def parse_handshake_line(line: str) -> HandshakePacket:
    """Parse a simple comma-separated handshake line.

    Format: HS,protocol_version,imu_sample_rate_hz,axis_order,tick_hz,frame_format
    """

    parts = line.strip().split(",")
    if len(parts) != 6 or parts[0] != "HS":
        raise ProtocolError("Invalid handshake packet format")
    return HandshakePacket(
        protocol_version=int(parts[1]),
        imu_sample_rate_hz=int(parts[2]),
        axis_order=parts[3],
        tick_hz=int(parts[4]),
        frame_format=parts[5],
    )


def parse_sample_line(line: str) -> IMUSamplePacket:
    """Parse a simple comma-separated IMU sample line.

    Format: IMU,seq,tick,ax,ay,az,gx,gy,gz,crc_ok
    """

    parts = line.strip().split(",")
    if len(parts) != 10 or parts[0] != "IMU":
        raise ProtocolError("Invalid IMU packet format")
    return IMUSamplePacket(
        imu_seq=int(parts[1]),
        t_imu_tick_us=int(parts[2]),
        ax=float(parts[3]),
        ay=float(parts[4]),
        az=float(parts[5]),
        gx=float(parts[6]),
        gy=float(parts[7]),
        gz=float(parts[8]),
        packet_crc_ok=parts[9] == "1",
    )


def validate_handshake(
    packet: HandshakePacket,
    *,
    expected_sample_rate_hz: int,
) -> None:
    """Validate critical handshake fields against runtime expectations."""

    if packet.imu_sample_rate_hz != expected_sample_rate_hz:
        message = (
            "Unexpected sample rate: "
            f"{packet.imu_sample_rate_hz}, expected {expected_sample_rate_hz}"
        )
        raise ProtocolError(
            message
        )
    if packet.protocol_version <= 0:
        raise ProtocolError("protocol_version must be positive")
