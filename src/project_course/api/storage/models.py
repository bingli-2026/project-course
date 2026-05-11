"""Pydantic response models for the samples API."""

from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel, Field


class SampleMetadata(BaseModel):
    sample_id: str
    label: str | None = None
    captured_at: str | None = None
    source_name: str | None = None
    has_vision: bool
    has_sensor: bool
    file_path: str
    window_count: int
    ingested_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "SampleMetadata":
        return cls(
            sample_id=row["sample_id"],
            label=row["label"],
            captured_at=row["captured_at"],
            source_name=row["source_name"],
            has_vision=bool(row["has_vision"]),
            has_sensor=bool(row["has_sensor"]),
            file_path=row["file_path"],
            window_count=row["window_count"],
            ingested_at=row["ingested_at"],
        )


class SampleDetail(BaseModel):
    metadata: SampleMetadata
    rows: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Window-level feature rows from the source file.",
    )


class SampleTimeseries(BaseModel):
    sample_id: str
    fields: list[str]
    points: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Each entry has center_time_s plus the requested feature fields.",
    )


class IngestError(BaseModel):
    detail: str
    missing_columns: list[str] = Field(default_factory=list)
