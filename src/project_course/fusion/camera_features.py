"""Vision displacement feature extraction utilities."""

from __future__ import annotations

import numpy as np
from scipy.signal import welch


def _vision_axis_features(
    signal: np.ndarray,
    analysis_fps: float,
    prefix: str,
) -> dict[str, float]:
    freqs, psd = welch(
        signal,
        fs=analysis_fps,
        nperseg=min(len(signal), 256),
    )
    if len(freqs) == 0:
        return {
            f"{prefix}_peak_hz": 0.0,
            f"{prefix}_peak_power": 0.0,
            f"{prefix}_band_power": 0.0,
            f"{prefix}_spectral_centroid_hz": 0.0,
            f"{prefix}_spectral_entropy": 0.0,
        }
    peak_idx = int(np.argmax(psd))
    band_power = float(np.sum(psd))
    centroid = float(np.sum(freqs * psd) / (band_power + 1e-12))
    norm = psd / (band_power + 1e-12)
    entropy = float(-np.sum(norm * np.log(norm + 1e-12)))
    return {
        f"{prefix}_peak_hz": float(freqs[peak_idx]),
        f"{prefix}_peak_power": float(psd[peak_idx]),
        f"{prefix}_band_power": band_power,
        f"{prefix}_spectral_centroid_hz": centroid,
        f"{prefix}_spectral_entropy": entropy,
    }


def extract_camera_features(
    dx: np.ndarray,
    dy: np.ndarray,
    analysis_fps: float,
) -> dict[str, float]:
    features: dict[str, float] = {}
    features.update(_vision_axis_features(dx, analysis_fps, "vision_dx"))
    features.update(_vision_axis_features(dy, analysis_fps, "vision_dy"))
    return features
