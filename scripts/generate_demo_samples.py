"""Generate synthetic feature CSVs that conform to doc/feature_schema.md.

Run from the repo root:

    uv run python scripts/generate_demo_samples.py

It writes 3 sample files (normal / unbalance / looseness) into data/samples/
so the dashboard has something to display before real teammate data arrives.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data" / "samples"

WINDOW_COUNT = 24
ANALYSIS_FPS = 420.0
WINDOW_DURATION_S = 0.5


def _row(sample_id: str, label: str, window_index: int, profile: dict) -> dict:
    rng = np.random.default_rng(seed=hash((sample_id, window_index)) & 0xFFFFFFFF)
    t = window_index * WINDOW_DURATION_S

    base_freq_x = profile["vision_dx"] + rng.normal(0, profile["jitter"])
    base_freq_y = profile["vision_dy"] + rng.normal(0, profile["jitter"])
    sensor_ax = profile["sensor_ax"] + rng.normal(0, profile["jitter"])
    sensor_ay = profile["sensor_ay"] + rng.normal(0, profile["jitter"])
    sensor_az = profile["sensor_az"] + rng.normal(0, profile["jitter"] * 0.5)

    return {
        # identity
        "sample_id": sample_id,
        "label": label,
        "modality": "fused",
        "source_name": f"{sample_id}.mp4",
        "window_index": window_index,
        "window_start_frame": window_index * 210,
        "window_end_frame": (window_index + 1) * 210,
        "center_time_s": round(t + WINDOW_DURATION_S / 2, 4),
        "analysis_fps": ANALYSIS_FPS,
        # vision
        "roi_x": 120,
        "roi_y": 80,
        "roi_w": 96,
        "roi_h": 64,
        "vision_dx_peak_hz": round(base_freq_x, 4),
        "vision_dy_peak_hz": round(base_freq_y, 4),
        "vision_dx_peak_power": round(profile["power_x"] + rng.normal(0, 0.05), 4),
        "vision_dy_peak_power": round(profile["power_y"] + rng.normal(0, 0.05), 4),
        "vision_dx_band_power": round(profile["power_x"] * 1.6, 4),
        "vision_dy_band_power": round(profile["power_y"] * 1.6, 4),
        "vision_dx_spectral_centroid_hz": round(base_freq_x * 1.1, 4),
        "vision_dy_spectral_centroid_hz": round(base_freq_y * 1.1, 4),
        "vision_dx_spectral_entropy": round(profile["entropy"] + rng.normal(0, 0.02), 4),
        "vision_dy_spectral_entropy": round(profile["entropy"] + rng.normal(0, 0.02), 4),
        # sensor — accelerometer spectrum (subset; full schema can be added later)
        "sensor_sample_rate_hz": 1600.0,
        "sensor_window_duration_s": WINDOW_DURATION_S,
        "sensor_ax_rms": round(profile["ax_rms"] + rng.normal(0, 0.01), 4),
        "sensor_ay_rms": round(profile["ay_rms"] + rng.normal(0, 0.01), 4),
        "sensor_az_rms": round(profile["az_rms"] + rng.normal(0, 0.005), 4),
        "sensor_ax_peak_hz": round(sensor_ax, 4),
        "sensor_ay_peak_hz": round(sensor_ay, 4),
        "sensor_az_peak_hz": round(sensor_az, 4),
        "sensor_ax_peak_power": round(profile["ax_rms"] ** 2, 4),
        "sensor_ay_peak_power": round(profile["ay_rms"] ** 2, 4),
        "sensor_az_peak_power": round(profile["az_rms"] ** 2, 4),
    }


PROFILES: dict[str, dict] = {
    "normal": {
        "vision_dx": 12.0, "vision_dy": 14.0,
        "sensor_ax": 50.0, "sensor_ay": 52.0, "sensor_az": 25.0,
        "power_x": 0.5, "power_y": 0.6, "entropy": 0.42,
        "ax_rms": 0.18, "ay_rms": 0.21, "az_rms": 0.09,
        "jitter": 0.4,
    },
    "unbalance": {
        "vision_dx": 24.5, "vision_dy": 26.0,
        "sensor_ax": 100.0, "sensor_ay": 104.0, "sensor_az": 50.0,
        "power_x": 1.4, "power_y": 1.6, "entropy": 0.31,
        "ax_rms": 0.62, "ay_rms": 0.71, "az_rms": 0.34,
        "jitter": 0.7,
    },
    "looseness": {
        "vision_dx": 18.0, "vision_dy": 19.5,
        "sensor_ax": 75.0, "sensor_ay": 80.0, "sensor_az": 40.0,
        "power_x": 0.9, "power_y": 1.1, "entropy": 0.58,
        "ax_rms": 0.40, "ay_rms": 0.45, "az_rms": 0.22,
        "jitter": 1.5,
    },
}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for label, profile in PROFILES.items():
        sample_id = f"demo_{label}"
        rows = [_row(sample_id, label, i, profile) for i in range(WINDOW_COUNT)]
        df = pd.DataFrame(rows)
        target = OUTPUT_DIR / f"{sample_id}.csv"
        df.to_csv(target, index=False)
        print(f"wrote {target} ({len(df)} rows)")


if __name__ == "__main__":
    main()
