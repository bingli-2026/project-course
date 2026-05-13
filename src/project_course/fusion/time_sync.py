"""Clock alignment helpers between MCU tick and host time."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SyncFitResult:
    """Linear fit result for host = a * imu_tick + b."""

    a: float
    b: float
    r2: float


def unwrap_ticks(ticks: list[int], *, modulus: int = 2**32) -> list[int]:
    """Unwrap wrapping tick sequence into a monotonic logical timeline."""

    if not ticks:
        return []
    unwrapped = [ticks[0]]
    offset = 0
    prev = ticks[0]
    for tick in ticks[1:]:
        if tick < prev:
            offset += modulus
        unwrapped.append(tick + offset)
        prev = tick
    return unwrapped


def fit_clock_map(imu_ticks_us: list[int], host_times_s: list[float]) -> SyncFitResult:
    """Fit a linear map from MCU tick (us) to host time (s)."""

    if len(imu_ticks_us) != len(host_times_s) or len(imu_ticks_us) < 3:
        raise ValueError("Need >=3 aligned samples and matching lengths")

    x = np.asarray(imu_ticks_us, dtype=np.float64)
    y = np.asarray(host_times_s, dtype=np.float64)
    a, b = np.polyfit(x, y, deg=1)
    y_pred = a * x + b
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 if ss_tot == 0.0 else 1.0 - ss_res / ss_tot
    return SyncFitResult(a=float(a), b=float(b), r2=r2)


def map_tick_to_host_time(tick_us: int, fit: SyncFitResult) -> float:
    """Project one MCU tick onto host time using fit coefficients."""

    return fit.a * float(tick_us) + fit.b
