"""Unit tests for STM32 protocol parsing."""

from __future__ import annotations

import pytest

from project_course.services.imu_protocol import (
    ProtocolError,
    parse_handshake_line,
    parse_sample_line,
    validate_handshake,
)


def test_parse_handshake_line() -> None:
    packet = parse_handshake_line("HS,1,1680,axayazgxgygz,1000000,YUY2")
    assert packet.protocol_version == 1
    assert packet.imu_sample_rate_hz == 1680


def test_validate_handshake_rejects_sample_rate_mismatch() -> None:
    packet = parse_handshake_line("HS,1,1600,axayazgxgygz,1000000,YUY2")
    with pytest.raises(ProtocolError):
        validate_handshake(packet, expected_sample_rate_hz=1680)


def test_parse_sample_line() -> None:
    sample = parse_sample_line("IMU,3,12345,0.1,0.2,0.3,0.4,0.5,0.6,1")
    assert sample.imu_seq == 3
    assert sample.packet_crc_ok is True
