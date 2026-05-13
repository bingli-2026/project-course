"""Incremental model update service with threshold guards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from project_course.api.config import settings
from project_course.services.model_registry import ModelRegistry


@dataclass(frozen=True)
class IncrementalUpdateRequest:
    base_model_version: str
    new_condition_name: str
    sample_count: int
    session_count: int


@dataclass(frozen=True)
class IncrementalUpdateResult:
    update_job_id: str
    model_version_after: str
    accepted: bool
    reason: str | None


class ModelUpdateService:
    """Applies threshold-guarded incremental update logic."""

    def __init__(self, registry: ModelRegistry) -> None:
        self._registry = registry

    def validate_threshold(self, request: IncrementalUpdateRequest) -> None:
        if request.sample_count < settings.incremental_min_windows:
            message = (
                "insufficient windows: "
                f"{request.sample_count} < {settings.incremental_min_windows}"
            )
            raise ValueError(message)
        if request.session_count < settings.incremental_min_sessions:
            message = (
                "insufficient sessions: "
                f"{request.session_count} < {settings.incremental_min_sessions}"
            )
            raise ValueError(message)

    def run_incremental_update(
        self,
        request: IncrementalUpdateRequest,
    ) -> IncrementalUpdateResult:
        self.validate_threshold(request)
        base = self._registry.latest()
        if base is None:
            self._registry.add_version(request.base_model_version, "baseline")
            base = self._registry.latest()

        assert base is not None
        next_idx = len(self._registry.list_versions()) + 1
        next_version = f"v0.1.{next_idx}"
        self._registry.add_version(next_version, "incremental")

        update_job_id = f"upd-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        return IncrementalUpdateResult(
            update_job_id=update_job_id,
            model_version_after=next_version,
            accepted=True,
            reason=None,
        )

    @staticmethod
    def build_report(*, before: str, after: str) -> dict[str, object]:
        """Build a lightweight comparison report placeholder."""

        return {
            "model_version_before": before,
            "model_version_after": after,
            "new_condition_metric": 0.82,
            "historical_metric": 0.78,
            "delta_new_condition": 0.22,
            "delta_historical": -0.03,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
