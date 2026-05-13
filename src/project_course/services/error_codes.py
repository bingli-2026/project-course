"""Shared runtime error codes and user-facing actions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCode:
    """One actionable error item."""

    code: str
    message: str
    action: str


IMU_STREAM_TIMEOUT = ErrorCode(
    code="imu_stream_timeout",
    message="串口在阈值时间内未收到数据",
    action="检查 STM32 供电、USB 线缆和波特率配置后重试",
)

CAMERA_FRAME_GAP = ErrorCode(
    code="camera_frame_gap",
    message="摄像头帧流中断",
    action="检查摄像头连接和曝光配置，重启采集任务",
)

DISK_SPACE_LOW = ErrorCode(
    code="disk_space_low",
    message="磁盘空间不足，无法启动任务",
    action="释放磁盘空间或调整输出目录后重试",
)
