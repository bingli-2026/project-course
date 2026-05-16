"""CLI for ATK-MS6DSV I2C validation and CSV capture."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from project_course.sensors.ms6dsv import MS6DSVError, MS6DSVI2CReader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ATK-MS6DSV I2C capture utility")
    parser.add_argument("--bus", type=int, default=7, help="I2C bus id (default: 7)")
    parser.add_argument(
        "--address",
        type=lambda x: int(x, 0),
        default=0x6A,
        help="I2C address in hex/dec (default: 0x6A)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/ms6dsv_capture.csv"),
        help="CSV output path",
    )
    parser.add_argument(
        "--duration-s",
        type=float,
        default=5.0,
        help="capture duration in seconds",
    )
    parser.add_argument(
        "--target-hz",
        type=float,
        default=480.0,
        help="target sample loop rate",
    )
    parser.add_argument(
        "--odr-hz",
        type=int,
        choices=[60, 120, 240, 480, 960, 1920],
        default=480,
        help="sensor ODR for accel/gyro (default: 480)",
    )
    parser.add_argument(
        "--benchmark-samples",
        type=int,
        default=2000,
        help="sample count for max-rate estimate",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=Path("artifacts/logs/ms6dsv_capture.log"),
        help="log file path",
    )
    parser.add_argument(
        "--strict-hardware",
        action="store_true",
        help="fail with non-zero exit code when hardware is unavailable",
    )
    return parser


def _setup_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("project_course.sensors.ms6dsv_cli")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logger = _setup_logger(args.log_path)
    logger.info(
        "ms6dsv capture start bus=%s address=0x%02X odr_hz=%s target_hz=%s duration_s=%s",
        args.bus,
        args.address,
        args.odr_hz,
        args.target_hz,
        args.duration_s,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        with MS6DSVI2CReader(bus=args.bus, address=args.address) as reader:
            reader.setup_default(odr_hz=args.odr_hz)
            max_rate = reader.estimate_rate_hz(sample_count=args.benchmark_samples)
            count, captured_rate = reader.capture_csv(
                output_path=args.output,
                duration_s=args.duration_s,
                target_hz=args.target_hz,
            )
            logger.info("estimated_max_rate_hz=%.2f", max_rate)
            logger.info("captured_samples=%s", count)
            logger.info("captured_rate_hz=%.2f", captured_rate)
            logger.info("csv_path=%s", args.output)
            return 0
    except (MS6DSVError, OSError, PermissionError) as exc:
        logger.warning("hardware_unavailable: %s", exc)
        logger.warning(
            "soft fallback: skip sensor capture so other modules can continue"
        )
        if args.strict_hardware:
            logger.error("strict-hardware mode enabled, exiting with code 2")
            return 2
        return 0


def main() -> None:
    raise SystemExit(run(sys.argv[1:]))
