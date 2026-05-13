"""Unit tests for time sync helpers."""

from __future__ import annotations

import numpy as np

from project_course.fusion.time_sync import fit_clock_map, unwrap_ticks


def test_unwrap_ticks_handles_overflow() -> None:
    ticks = [4294967290, 4294967294, 2, 10]
    out = unwrap_ticks(ticks)
    assert out == [4294967290, 4294967294, 4294967298, 4294967306]


def test_fit_clock_map_high_r2_for_linear_signal() -> None:
    x = np.arange(0, 6720, dtype=np.int64) * 595
    y = 0.000001 * x + 10.0
    fit = fit_clock_map(x.tolist(), y.tolist())
    assert fit.r2 > 0.999
