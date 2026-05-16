"""STM32 CDC protocol parsing and validation."""

from __future__ import annotations

import struct
from dataclasses import dataclass

BINARY34_FRAME_SIZE = 34
BINARY34_PAYLOAD_SIZE = 32
DEFAULT_FRAME_FORMAT = "binary34"
DEFAULT_TICK_HZ = 1_000_000


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


def crc16_modbus(data: bytes) -> int:
    """Compute MODBUS CRC16 (poly 0xA001, init 0xFFFF)."""

    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if (crc & 0x0001) != 0:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


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


def parse_binary34_frame(frame: bytes) -> IMUSamplePacket:
    """Parse fixed-size binary34 frame.

    Layout (little-endian, 34 bytes total):
    - seq: u32
    - tick_us: u32
    - ax..gz: 6 * float32
    - crc16: u16 over first 32 bytes
    """

    if len(frame) != BINARY34_FRAME_SIZE:
        raise ProtocolError(
            f"Invalid binary34 frame size: {len(frame)}, expected {BINARY34_FRAME_SIZE}"
        )

    payload = frame[:BINARY34_PAYLOAD_SIZE]
    wire_crc = struct.unpack("<H", frame[BINARY34_PAYLOAD_SIZE:])[0]
    calc_crc = crc16_modbus(payload)
    seq, tick_us, ax, ay, az, gx, gy, gz = struct.unpack("<IIffffff", payload)

    return IMUSamplePacket(
        imu_seq=seq,
        t_imu_tick_us=tick_us,
        ax=ax,
        ay=ay,
        az=az,
        gx=gx,
        gy=gy,
        gz=gz,
        packet_crc_ok=wire_crc == calc_crc,
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


def parse_sample_packet(raw: bytes, *, frame_format: str) -> IMUSamplePacket:
    """Parse one sample packet according to handshake frame format."""

    if frame_format == DEFAULT_FRAME_FORMAT:
        return parse_binary34_frame(raw)
    raise ProtocolError(f"Unsupported frame_format: {frame_format}")


def validate_handshake(
    packet: HandshakePacket,
    *,
    expected_sample_rate_hz: int,
    expected_frame_format: str = DEFAULT_FRAME_FORMAT,
    expected_tick_hz: int = DEFAULT_TICK_HZ,
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
    if packet.tick_hz != expected_tick_hz:
        raise ProtocolError(
            f"Unexpected tick_hz: {packet.tick_hz}, expected {expected_tick_hz}"
        )
    if packet.frame_format != expected_frame_format:
        raise ProtocolError(
            "Unexpected frame_format: "
            f"{packet.frame_format}, expected {expected_frame_format}"
        )
