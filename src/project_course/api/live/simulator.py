"""Synthetic window-sample generator used when no real pipeline is attached.

The simulator runs as a background asyncio task during dev. Whenever a task is
active in `LIVE_STATE`, it appends a new window every `settings.simulator_tick_s`
seconds with realistic-looking dual-modal features. It also periodically
publishes synthetic sync-quality metrics.

This module has no knowledge of HTTP — it talks only to `live.publish_window`
and `live.record_sync_quality`, exactly the same hooks the real feature
pipeline will use.
"""

from __future__ import annotations

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from typing import AsyncIterator

import numpy as np

from project_course.api.config import settings
from project_course.api.live import publish_window, record_sync_quality
from project_course.api.live.state import LIVE_STATE

logger = logging.getLogger(__name__)


PROFILES: dict[str, dict[str, float]] = {
    "normal": {"vision_dx": 12.0, "vision_dy": 14.0, "sensor_ax": 50.0, "sensor_ay": 52.0, "sensor_az": 25.0, "power": 0.5, "jitter": 0.4, "conf": 0.92},
    "unbalance": {"vision_dx": 24.5, "vision_dy": 26.0, "sensor_ax": 100.0, "sensor_ay": 104.0, "sensor_az": 50.0, "power": 1.4, "jitter": 0.7, "conf": 0.88},
    "loose": {"vision_dx": 18.0, "vision_dy": 19.5, "sensor_ax": 75.0, "sensor_ay": 80.0, "sensor_az": 40.0, "power": 0.9, "jitter": 1.5, "conf": 0.78},
    "misaligned": {"vision_dx": 30.0, "vision_dy": 31.5, "sensor_ax": 88.0, "sensor_ay": 90.0, "sensor_az": 45.0, "power": 1.1, "jitter": 0.9, "conf": 0.82},
}


def _synth_window(window_index: int, task_id: str, profile_name: str) -> dict:
    profile = PROFILES[profile_name]
    rng = np.random.default_rng(seed=hash((task_id, window_index)) & 0xFFFFFFFF)
    j = profile["jitter"]
    return {
        "sample_id": task_id,
        "label": profile_name,
        "modality": "fused",
        "source_name": f"simulator://{task_id}",
        "window_index": window_index,
        "window_start_frame": window_index * 210,
        "window_end_frame": (window_index + 1) * 210,
        "center_time_s": round(window_index * settings.window_hop_s + settings.window_size_s / 2, 4),
        "analysis_fps": settings.analysis_fps,
        "imu_quality_flag": "ok",
        "cam_quality_flag": "ok",
        "sync_fit_failed": False,
        "seq_gap_count": 0,
        # vision
        "vision_dx_peak_hz": round(profile["vision_dx"] + rng.normal(0, j), 3),
        "vision_dy_peak_hz": round(profile["vision_dy"] + rng.normal(0, j), 3),
        "vision_dx_peak_power": round(profile["power"] + rng.normal(0, 0.05), 4),
        "vision_dy_peak_power": round(profile["power"] * 1.05 + rng.normal(0, 0.05), 4),
        # sensor accel spectrum
        "sensor_ax_peak_hz": round(profile["sensor_ax"] + rng.normal(0, j), 3),
        "sensor_ay_peak_hz": round(profile["sensor_ay"] + rng.normal(0, j), 3),
        "sensor_az_peak_hz": round(profile["sensor_az"] + rng.normal(0, j * 0.5), 3),
        "sensor_ax_peak_power": round(profile["power"] ** 2 + rng.normal(0, 0.05), 4),
        "sensor_ay_peak_power": round(profile["power"] ** 2 * 1.1 + rng.normal(0, 0.05), 4),
        "sensor_az_peak_power": round(profile["power"] ** 2 * 0.4 + rng.normal(0, 0.03), 4),
        # sensor gyro spectrum (lower amplitude variants)
        "sensor_gx_peak_hz": round(profile["sensor_ax"] * 0.6 + rng.normal(0, j), 3),
        "sensor_gy_peak_hz": round(profile["sensor_ay"] * 0.6 + rng.normal(0, j), 3),
        "sensor_gz_peak_hz": round(profile["sensor_az"] * 0.6 + rng.normal(0, j * 0.5), 3),
        "sensor_gx_peak_power": round(profile["power"] * 0.3 + rng.normal(0, 0.03), 4),
        "sensor_gy_peak_power": round(profile["power"] * 0.3 + rng.normal(0, 0.03), 4),
        "sensor_gz_peak_power": round(profile["power"] * 0.15 + rng.normal(0, 0.02), 4),
        # fused display
        "fused_dominant_freq_hz": round((profile["vision_dx"] + profile["sensor_ax"]) / 2 + rng.normal(0, j), 3),
        "fusion_confidence": round(min(1.0, max(0.0, profile["conf"] + rng.normal(0, 0.04))), 3),
        # rolling prediction
        "predicted_state": profile_name,
        "prediction_confidence": round(min(1.0, max(0.0, profile["conf"] + rng.normal(0, 0.04))), 3),
    }


async def _simulator_loop() -> None:
    """Continuously produce synthetic windows when a task is active."""
    window_index = 0
    sync_tick = 0
    profile_name = "normal"
    profile_remaining = random.randint(20, 40)
    while True:
        try:
            active = LIVE_STATE.active_task
            if active is None:
                window_index = 0
                sync_tick = 0
                await asyncio.sleep(settings.simulator_tick_s)
                continue

            if profile_remaining <= 0:
                profile_name = random.choice(list(PROFILES.keys()))
                profile_remaining = random.randint(20, 50)
            else:
                profile_remaining -= 1

            payload = _synth_window(window_index, active.task_id, profile_name)
            publish_window(payload)

            sync_tick += 1
            if sync_tick % 4 == 0:
                record_sync_quality(
                    offset_ms_p95=round(random.uniform(0.6, 1.8), 2),
                    drift_ppm=round(random.uniform(1.5, 4.5), 2),
                    aligned_window_ratio=round(random.uniform(0.92, 0.99), 3),
                )

            window_index += 1
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("simulator tick failed")
        await asyncio.sleep(settings.simulator_tick_s)


@asynccontextmanager
async def simulator_lifespan() -> AsyncIterator[None]:
    """Start the simulator alongside the FastAPI app and cancel it on shutdown."""
    if not settings.simulator_enabled:
        yield
        return
    task = asyncio.create_task(_simulator_loop(), name="window-simulator")
    logger.info("window simulator started (tick=%ss)", settings.simulator_tick_s)
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info("window simulator stopped")
