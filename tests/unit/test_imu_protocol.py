"""Unit tests for STM32 protocol parsing."""

from __future__ import annotations

import struct

import pytest

from project_course.services.imu_protocol import (
    BINARY34_FRAME_SIZE,
    ProtocolError,
    crc16_modbus,
    parse_binary34_frame,
    parse_handshake_line,
    parse_sample_line,
    parse_sample_packet,
    validate_handshake,
)


def test_parse_handshake_line() -> None:
    packet = parse_handshake_line("HS,1,1680,ax|ay|az|gx|gy|gz,1000000,binary34")
    assert packet.protocol_version == 1
    assert packet.imu_sample_rate_hz == 1680
    assert packet.frame_format == "binary34"


def test_validate_handshake_rejects_sample_rate_mismatch() -> None:
    packet = parse_handshake_line("HS,1,1600,ax|ay|az|gx|gy|gz,1000000,binary34")
    with pytest.raises(ProtocolError):
        validate_handshake(packet, expected_sample_rate_hz=1680)


def test_validate_handshake_rejects_frame_format_mismatch() -> None:
    packet = parse_handshake_line("HS,1,1680,ax|ay|az|gx|gy|gz,1000000,csv")
    with pytest.raises(ProtocolError):
        validate_handshake(packet, expected_sample_rate_hz=1680)


def test_parse_sample_line() -> None:
    sample = parse_sample_line("IMU,3,12345,0.1,0.2,0.3,0.4,0.5,0.6,1")
    assert sample.imu_seq == 3
    assert sample.packet_crc_ok is True


def test_parse_binary34_frame() -> None:
    payload = struct.pack(
        "<IIffffff",
        7,
        123456,
        0.1,
        0.2,
        0.3,
        0.4,
        0.5,
        0.6,
    )
    frame = payload + struct.pack("<H", crc16_modbus(payload))
    assert len(frame) == BINARY34_FRAME_SIZE

    sample = parse_binary34_frame(frame)
    assert sample.imu_seq == 7
    assert sample.t_imu_tick_us == 123456
    assert sample.packet_crc_ok is True


def test_parse_binary34_frame_crc_mismatch_marks_bad_crc() -> None:
    payload = struct.pack(
        "<IIffffff",
        1,
        2,
        1.0,
        2.0,
        3.0,
        4.0,
        5.0,
        6.0,
    )
    bad_crc = 0x0000
    frame = payload + struct.pack("<H", bad_crc)
    sample = parse_binary34_frame(frame)
    assert sample.packet_crc_ok is False


def test_parse_binary34_frame_rejects_invalid_length() -> None:
    with pytest.raises(ProtocolError):
        parse_binary34_frame(b"\x00" * 33)


def test_parse_sample_packet_dispatch_binary34() -> None:
    payload = struct.pack(
        "<IIffffff",
        11,
        22,
        0.11,
        0.22,
        0.33,
        0.44,
        0.55,
        0.66,
    )
    frame = payload + struct.pack("<H", crc16_modbus(payload))
    sample = parse_sample_packet(frame, frame_format="binary34")
    assert sample.imu_seq == 11


def test_parse_sample_packet_rejects_unsupported_format() -> None:
    with pytest.raises(ProtocolError):
        parse_sample_packet(b"", frame_format="csv")
