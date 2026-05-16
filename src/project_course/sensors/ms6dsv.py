"""LSM6DSV16X (ATK-MS6DSV) I2C capture helpers."""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path

WHO_AM_I_EXPECT = 0x70

REG_WHO_AM_I = 0x0F
REG_CTRL1 = 0x10
REG_CTRL2 = 0x11
REG_CTRL3 = 0x12
REG_CTRL6 = 0x15
REG_CTRL8 = 0x17
REG_STATUS = 0x1E
REG_OUTX_L_G = 0x22
REG_OUTX_L_A = 0x28

ODR_REG_BY_HZ = {
    60: 0x05,
    120: 0x06,
    240: 0x07,
    480: 0x08,
    960: 0x09,
    1920: 0x0A,
}
FS_G_2000DPS = 0x04
FS_XL_2G = 0x00


@dataclass(frozen=True)
class MS6DSVSample:
    """One raw 6-axis sample."""

    host_time_us: int
    status: int
    gx: int
    gy: int
    gz: int
    ax: int
    ay: int
    az: int


class MS6DSVError(RuntimeError):
    """Raised when sensor setup/read fails."""


def _to_i16(lo: int, hi: int) -> int:
    value = (hi << 8) | lo
    return value - 65536 if value & 0x8000 else value


class MS6DSVI2CReader:
    """I2C reader for ATK-MS6DSV using burst 12-byte reads."""

    def __init__(self, *, bus: int = 7, address: int = 0x6A) -> None:
        self._bus_id = bus
        self._address = address
        self._bus = None

    def __enter__(self) -> MS6DSVI2CReader:
        try:
            from smbus2 import SMBus  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise MS6DSVError("smbus2 is required for MS6DSV I2C capture") from exc

        self._bus = SMBus(self._bus_id)
        return self

    def __exit__(self, *_: object) -> None:
        if self._bus is not None:
            self._bus.close()
        self._bus = None

    def setup_default(self, *, odr_hz: int = 480) -> None:
        """Configure a known-good profile.

        Defaults to 480 Hz because this is the highest stable no-overrun point
        observed on current Orange Pi I2C capture experiments.
        """

        odr_reg = ODR_REG_BY_HZ.get(odr_hz)
        if odr_reg is None:
            raise MS6DSVError(
                f"Unsupported odr_hz={odr_hz}, choose one of "
                f"{sorted(ODR_REG_BY_HZ.keys())}"
            )

        who = self.read_register(REG_WHO_AM_I)
        if who != WHO_AM_I_EXPECT:
            raise MS6DSVError(
                f"Unexpected WHO_AM_I: 0x{who:02X}, expected 0x{WHO_AM_I_EXPECT:02X}"
            )

        self.update_bits(REG_CTRL3, 0x44, 0x44)  # BDU=1, IF_INC=1
        self.update_bits(REG_CTRL1, 0x0F, odr_reg)
        self.update_bits(REG_CTRL2, 0x0F, odr_reg)
        self.update_bits(REG_CTRL6, 0x0F, FS_G_2000DPS)
        self.update_bits(REG_CTRL8, 0x03, FS_XL_2G)

    def read_sample(self) -> MS6DSVSample:
        """Read one sample: status + gyro + accel."""

        status = self.read_register(REG_STATUS)
        gyro = self.read_block(REG_OUTX_L_G, 6)
        accel = self.read_block(REG_OUTX_L_A, 6)
        gx = _to_i16(gyro[0], gyro[1])
        gy = _to_i16(gyro[2], gyro[3])
        gz = _to_i16(gyro[4], gyro[5])
        ax = _to_i16(accel[0], accel[1])
        ay = _to_i16(accel[2], accel[3])
        az = _to_i16(accel[4], accel[5])
        return MS6DSVSample(
            host_time_us=time.monotonic_ns() // 1000,
            status=status,
            gx=gx,
            gy=gy,
            gz=gz,
            ax=ax,
            ay=ay,
            az=az,
        )

    def estimate_rate_hz(self, *, sample_count: int = 2000) -> float:
        """Estimate maximum loop rate with burst reads."""

        start = time.perf_counter()
        for _ in range(sample_count):
            self.read_block(REG_OUTX_L_G, 12)
        elapsed = time.perf_counter() - start
        if elapsed <= 0:
            raise MS6DSVError("Invalid elapsed time while estimating sample rate")
        return sample_count / elapsed

    def capture_csv(
        self,
        *,
        output_path: str | Path,
        duration_s: float,
        target_hz: float,
    ) -> tuple[int, float]:
        """Capture samples for duration and write raw values to CSV."""

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        period_s = 1.0 / target_hz
        count = 0
        t_start = time.monotonic()
        next_deadline = t_start
        with output.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(
                [
                    "host_time_us",
                    "status",
                    "gx",
                    "gy",
                    "gz",
                    "ax",
                    "ay",
                    "az",
                ]
            )
            while True:
                now = time.monotonic()
                if now - t_start >= duration_s:
                    break
                sample = self.read_sample()
                writer.writerow(
                    [
                        sample.host_time_us,
                        sample.status,
                        sample.gx,
                        sample.gy,
                        sample.gz,
                        sample.ax,
                        sample.ay,
                        sample.az,
                    ]
                )
                count += 1
                next_deadline += period_s
                sleep_s = next_deadline - time.monotonic()
                if sleep_s > 0:
                    time.sleep(sleep_s)
        elapsed = time.monotonic() - t_start
        rate_hz = count / elapsed if elapsed > 0 else 0.0
        return count, rate_hz

    def update_bits(self, register: int, mask: int, value: int) -> None:
        current = self.read_register(register)
        updated = (current & ~mask) | (value & mask)
        self.write_register(register, updated)

    def read_register(self, register: int) -> int:
        bus = self._ensure_bus()
        return int(bus.read_byte_data(self._address, register))

    def write_register(self, register: int, value: int) -> None:
        bus = self._ensure_bus()
        bus.write_byte_data(self._address, register, value & 0xFF)

    def read_block(self, register: int, length: int) -> list[int]:
        bus = self._ensure_bus()
        return list(bus.read_i2c_block_data(self._address, register, length))

    def _ensure_bus(self):
        if self._bus is None:
            raise MS6DSVError("Reader is not opened. Use context manager.")
        return self._bus
