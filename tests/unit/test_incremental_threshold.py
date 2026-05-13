"""Unit tests for incremental update threshold guard."""

from __future__ import annotations

import pytest

from project_course.services.model_registry import ModelRegistry
from project_course.services.model_update_service import (
    IncrementalUpdateRequest,
    ModelUpdateService,
)


def test_incremental_threshold_rejects_low_sample_count() -> None:
    svc = ModelUpdateService(ModelRegistry())
    req = IncrementalUpdateRequest(
        base_model_version="v0.1.0",
        new_condition_name="misaligned",
        sample_count=10,
        session_count=3,
    )
    with pytest.raises(ValueError):
        svc.validate_threshold(req)


def test_incremental_threshold_rejects_low_session_count() -> None:
    svc = ModelUpdateService(ModelRegistry())
    req = IncrementalUpdateRequest(
        base_model_version="v0.1.0",
        new_condition_name="misaligned",
        sample_count=120,
        session_count=1,
    )
    with pytest.raises(ValueError):
        svc.validate_threshold(req)
