"""Model version registry primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ModelVersionRecord:
    """Tracks a model version and metadata."""

    model_version: str
    update_type: str
    created_at: str


class ModelRegistry:
    """In-memory foundational registry for model versions."""

    def __init__(self) -> None:
        self._versions: list[ModelVersionRecord] = []

    def add_version(
        self,
        model_version: str,
        update_type: str = "baseline",
    ) -> ModelVersionRecord:
        record = ModelVersionRecord(
            model_version=model_version,
            update_type=update_type,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._versions.append(record)
        return record

    def latest(self) -> ModelVersionRecord | None:
        return self._versions[-1] if self._versions else None

    def list_versions(self) -> list[ModelVersionRecord]:
        return list(self._versions)
