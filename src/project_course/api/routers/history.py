"""Offline history (renamed from v0 /samples) — /api/v1/history/*.

This route serves CSV/Parquet files dropped into `data/samples/`. Useful for
demo rehearsals when real hardware isn't connected. Not used by the live
dashboard.
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from project_course.api.config import settings
from project_course.api.storage import db
from project_course.api.storage.ingest import (
    SUPPORTED_SUFFIXES,
    IngestValidationError,
    ingest_file,
    read_feature_file,
    resolve_stored_path,
)
from project_course.api.storage.models import (
    HistoryDetail,
    HistoryMetadata,
    HistoryTimeseries,
)

router = APIRouter(prefix="/api/v1/history", tags=["history"])

DEFAULT_TIMESERIES_FIELDS = (
    "vision_dx_peak_hz",
    "vision_dy_peak_hz",
    "sensor_ax_peak_hz",
    "sensor_ay_peak_hz",
    "sensor_az_peak_hz",
)


def _df_records(df, columns: list[str]) -> list[dict[str, Any]]:
    subset = df[columns]
    records = subset.to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                record[key] = None
    return records


@router.post(
    "",
    summary="Upload an offline feature file",
    response_model=HistoryMetadata,
    status_code=status.HTTP_201_CREATED,
)
async def upload_history(file: UploadFile = File(...)) -> HistoryMetadata:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported file type {suffix!r}; expected .csv or .parquet",
        )

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    target = settings.data_dir / Path(file.filename).name
    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        ingest_file(target)
    except IngestValidationError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail={
                "message": exc.detail,
                "missing_columns": exc.missing_columns,
            },
        ) from exc

    df = read_feature_file(target)
    sample_id = str(df["sample_id"].iloc[0])
    row = db.get_history(sample_id)
    if row is None:
        raise HTTPException(
            status_code=500,
            detail="ingest succeeded but metadata row not found",
        )
    return HistoryMetadata.from_row(row)


@router.delete("/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(sample_id: str) -> None:
    row = db.get_history(sample_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"history {sample_id} not found")
    file_path = resolve_stored_path(row["file_path"])
    file_path.unlink(missing_ok=True)
    db.delete_history(sample_id)


@router.get("", summary="List ingested history samples", response_model=list[HistoryMetadata])
def list_history(
    label: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[HistoryMetadata]:
    rows = db.list_history(label=label, limit=limit, offset=offset)
    return [HistoryMetadata.from_row(r) for r in rows]


@router.get(
    "/{sample_id}",
    summary="Get history metadata and all window rows",
    response_model=HistoryDetail,
)
def get_history(sample_id: str) -> HistoryDetail:
    row = db.get_history(sample_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"history {sample_id} not found")
    metadata = HistoryMetadata.from_row(row)
    file_path = resolve_stored_path(row["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=410, detail=f"file missing on disk: {file_path}")
    df = read_feature_file(file_path)
    return HistoryDetail(metadata=metadata, rows=_df_records(df, list(df.columns)))


@router.get(
    "/{sample_id}/timeseries",
    summary="Window-level timeseries for selected feature fields",
    response_model=HistoryTimeseries,
)
def get_history_timeseries(
    sample_id: str,
    fields: list[str] | None = Query(default=None),
) -> HistoryTimeseries:
    row = db.get_history(sample_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"history {sample_id} not found")
    file_path = resolve_stored_path(row["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=410, detail=f"file missing on disk: {file_path}")
    df = read_feature_file(file_path)
    requested = list(fields) if fields else list(DEFAULT_TIMESERIES_FIELDS)
    available = [f for f in requested if f in df.columns]
    columns = ["center_time_s", *available]
    return HistoryTimeseries(
        sample_id=sample_id,
        fields=available,
        points=_df_records(df.sort_values("center_time_s"), columns),
    )
