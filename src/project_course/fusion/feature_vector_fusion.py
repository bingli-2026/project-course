"""Feature vector join and fusion helpers."""

from __future__ import annotations


def build_fused_feature_vector(window_features: dict[str, float]) -> list[float]:
    """Create a stable feature vector from schema-aligned feature dictionary."""

    keys = sorted(
        key
        for key, value in window_features.items()
        if (
            key.startswith("vision_") or key.startswith("sensor_")
        )
        and isinstance(value, (int, float))
    )
    return [float(window_features[key]) for key in keys]


def compute_display_fused_frequency(
    window_features: dict[str, float],
) -> tuple[float, float]:
    """Compute display-only fused dominant frequency and confidence."""

    candidate_keys = [
        "vision_dx_peak_hz",
        "vision_dy_peak_hz",
        "sensor_ax_peak_hz",
        "sensor_ay_peak_hz",
        "sensor_az_peak_hz",
        "sensor_gx_peak_hz",
        "sensor_gy_peak_hz",
        "sensor_gz_peak_hz",
    ]
    values = [float(window_features[k]) for k in candidate_keys if k in window_features]
    if not values:
        return 0.0, 0.0
    mean_freq = sum(values) / len(values)
    spread = max(values) - min(values)
    confidence = max(0.0, min(1.0, 1.0 - spread / (mean_freq + 1e-6)))
    return mean_freq, confidence
