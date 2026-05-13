"""IMU per-axis feature extraction utilities."""

from __future__ import annotations

import numpy as np
from scipy.signal import welch
from scipy.stats import kurtosis


def _spectrum_features(signal: np.ndarray, sample_rate_hz: float) -> dict[str, float]:
    freqs, psd = welch(signal, fs=sample_rate_hz, nperseg=min(len(signal), 256))
    if len(freqs) == 0:
        return {
            "peak_hz": 0.0,
            "peak_power": 0.0,
            "band_power": 0.0,
            "spectral_centroid_hz": 0.0,
            "spectral_entropy": 0.0,
        }
    peak_idx = int(np.argmax(psd))
    band_power = float(np.sum(psd))
    centroid = float(np.sum(freqs * psd) / (band_power + 1e-12))
    norm = psd / (band_power + 1e-12)
    entropy = float(-np.sum(norm * np.log(norm + 1e-12)))
    return {
        "peak_hz": float(freqs[peak_idx]),
        "peak_power": float(psd[peak_idx]),
        "band_power": band_power,
        "spectral_centroid_hz": centroid,
        "spectral_entropy": entropy,
    }


def _time_features(signal: np.ndarray) -> dict[str, float]:
    return {
        "rms": float(np.sqrt(np.mean(signal**2))),
        "peak_to_peak": float(np.max(signal) - np.min(signal)),
        "kurtosis": float(kurtosis(signal, fisher=False, bias=False)),
    }


def extract_axis_features(
    signal: np.ndarray,
    sample_rate_hz: float,
    prefix: str,
) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in _time_features(signal).items():
        out[f"{prefix}_{key}"] = value
    for key, value in _spectrum_features(signal, sample_rate_hz).items():
        out[f"{prefix}_{key}"] = value
    return out


def extract_imu_features(
    window: dict[str, np.ndarray],
    sample_rate_hz: float,
) -> dict[str, float]:
    features: dict[str, float] = {}
    for axis in ("ax", "ay", "az", "gx", "gy", "gz"):
        prefix = f"sensor_{axis}"
        features.update(
            extract_axis_features(window[axis], sample_rate_hz, prefix)
        )
    features["sensor_sample_rate_hz"] = float(sample_rate_hz)
    return features
