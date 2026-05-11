"""SQLite metadata index for ingested samples."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from project_course.api.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    sample_id    TEXT PRIMARY KEY,
    label        TEXT,
    captured_at  TEXT,
    source_name  TEXT,
    has_vision   INTEGER NOT NULL,
    has_sensor   INTEGER NOT NULL,
    file_path    TEXT NOT NULL,
    window_count INTEGER NOT NULL,
    ingested_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_samples_label ON samples(label);
CREATE INDEX IF NOT EXISTS idx_samples_captured ON samples(captured_at);
"""


def _resolve_db_path() -> Path:
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_resolve_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)


def list_samples(
    label: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM samples"
    args: list[object] = []
    if label is not None:
        sql += " WHERE label = ?"
        args.append(label)
    sql += " ORDER BY ingested_at DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    with connect() as conn:
        return list(conn.execute(sql, args))


def get_sample(sample_id: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM samples WHERE sample_id = ?", (sample_id,)
        ).fetchone()


def upsert_sample(row: dict) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO samples (
                sample_id, label, captured_at, source_name,
                has_vision, has_sensor, file_path, window_count, ingested_at
            ) VALUES (
                :sample_id, :label, :captured_at, :source_name,
                :has_vision, :has_sensor, :file_path, :window_count, :ingested_at
            )
            ON CONFLICT(sample_id) DO UPDATE SET
                label=excluded.label,
                captured_at=excluded.captured_at,
                source_name=excluded.source_name,
                has_vision=excluded.has_vision,
                has_sensor=excluded.has_sensor,
                file_path=excluded.file_path,
                window_count=excluded.window_count,
                ingested_at=excluded.ingested_at
            """,
            row,
        )


def delete_sample(sample_id: str) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            "DELETE FROM samples WHERE sample_id = ?", (sample_id,)
        )
        return cursor.rowcount > 0
