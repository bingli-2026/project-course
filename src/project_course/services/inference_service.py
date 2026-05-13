"""Baseline inference service for fused feature vectors."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class InferenceResult:
    predicted_state: str
    confidence_summary: float


class InferenceService:
    """Simple rule-based baseline placeholder for US1 integration.

    This class exposes a stable service boundary before plugging in RF/XGBoost.
    """

    def predict(self, feature_vectors: list[list[float]]) -> InferenceResult:
        if not feature_vectors:
            return InferenceResult(predicted_state="unknown", confidence_summary=0.0)

        arr = np.asarray(feature_vectors, dtype=float)
        score = float(np.mean(arr)) if arr.size else 0.0
        if score < 0.2:
            label = "normal"
        elif score < 0.6:
            label = "unbalance"
        else:
            label = "loose"

        confidence = max(0.0, min(1.0, abs(score) / (abs(score) + 1.0)))
        return InferenceResult(predicted_state=label, confidence_summary=confidence)
