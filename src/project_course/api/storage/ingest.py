"""Ingest CSV/Parquet feature files into the metadata index."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from project_course.api.config import settings
from project_course.api.storage import db

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ("sample_id", "window_index", "center_time_s")
SUPPORTED_SUFFIXES = (".csv", ".parquet")
VISION_PREFIX = "vision_"
SENSOR_PREFIX = "sensor_"


class IngestValidationError(ValueError):
    """Raised when a feature file fails schema validation."""

    def __init__(self, detail: str, missing_columns: list[str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.missing_columns = missing_columns or []


@dataclass
class IngestResult:
    sample_id: str
    file_path: Path
    window_count: int
    has_vision: bool
    has_sensor: bool
    label: str | None


def read_feature_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise IngestValidationError(
        f"unsupported file extension {suffix!r}; expected .csv or .parquet",
    )


def validate_schema(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise IngestValidationError(
            f"missing required columns: {', '.join(missing)}",
            missing_columns=missing,
        )
    if df.empty:
        raise IngestValidationError("feature file contains no rows")
    distinct_ids = df["sample_id"].dropna().unique().tolist()
    if len(distinct_ids) != 1:
        raise IngestValidationError(
            f"file must contain exactly one sample_id, found {len(distinct_ids)}",
        )


def _has_populated_columns(df: pd.DataFrame, prefix: str) -> bool:
    matching = [c for c in df.columns if c.startswith(prefix)]
    if not matching:
        return False
    return bool(df[matching].notna().any().any())


def ingest_file(path: Path) -> IngestResult:
    df = read_feature_file(path)
    validate_schema(df)

    sample_id = str(df["sample_id"].iloc[0])
    label_series = df["label"].dropna() if "label" in df.columns else pd.Series(dtype=object)
    label = str(label_series.iloc[0]) if not label_series.empty else None
    has_vision = _has_populated_columns(df, VISION_PREFIX)
    has_sensor = _has_populated_columns(df, SENSOR_PREFIX)

    captured_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    ingested_at = datetime.now(tz=timezone.utc).isoformat()

    try:
        rel_path = path.resolve().relative_to(settings.data_dir.resolve())
        stored_path = str(rel_path).replace("\\", "/")
    except ValueError:
        stored_path = str(path.resolve())

    source_name = (
        str(df["source_name"].dropna().iloc[0])
        if "source_name" in df.columns and not df["source_name"].dropna().empty
        else path.name
    )

    db.upsert_history(
        {
            "sample_id": sample_id,
            "label": label,
            "captured_at": captured_at,
            "source_name": source_name,
            "has_vision": int(has_vision),
            "has_sensor": int(has_sensor),
            "file_path": stored_path,
            "window_count": int(len(df)),
            "ingested_at": ingested_at,
        }
    )
    return IngestResult(
        sample_id=sample_id,
        file_path=path,
        window_count=int(len(df)),
        has_vision=has_vision,
        has_sensor=has_sensor,
        label=label,
    )


def resolve_stored_path(file_path: str) -> Path:
    """Map a stored file_path back to an absolute Path."""
    candidate = Path(file_path)
    if candidate.is_absolute():
        return candidate
    return (settings.data_dir / candidate).resolve()


def scan_directory(data_dir: Path | None = None) -> list[IngestResult]:
    """Scan the data directory and ingest any new or modified feature files."""
    base = Path(data_dir) if data_dir else settings.data_dir
    base.mkdir(parents=True, exist_ok=True)
    results: list[IngestResult] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            results.append(ingest_file(path))
        except IngestValidationError as exc:
            logger.warning("skipping %s: %s", path, exc.detail)
        except Exception:  # noqa: BLE001
            logger.exception("failed to ingest %s", path)
    return results
