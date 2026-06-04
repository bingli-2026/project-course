"""CLI for ATK-MS6DSV I2C validation and CSV capture."""

from __future__ import annotations

import argparse
from pathlib import Path

from project_course.sensors.ms6dsv import DEFAULT_TARGET_HZ, MS6DSVI2CReader


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
        default=DEFAULT_TARGET_HZ,
        help="target host-side polling rate",
    )
    parser.add_argument(
        "--benchmark-samples",
        type=int,
        default=2000,
        help="sample count for max-rate estimate",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    with MS6DSVI2CReader(bus=args.bus, address=args.address) as reader:
        reader.setup_default()
        max_rate = reader.estimate_rate_hz(sample_count=args.benchmark_samples)
        print(f"estimated_max_rate_hz={max_rate:.2f}")
        count, captured_rate = reader.capture_csv(
            output_path=args.output,
            duration_s=args.duration_s,
            target_hz=args.target_hz,
        )
        print(f"captured_samples={count}")
        print(f"captured_rate_hz={captured_rate:.2f}")
        print(f"csv_path={args.output}")


if __name__ == "__main__":
    main()
