"""SQLite metadata index for tasks, window samples, and offline history."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from project_course.api.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id              TEXT PRIMARY KEY,
    task_status          TEXT NOT NULL,
    created_at           TEXT NOT NULL,
    started_at           TEXT,
    finished_at          TEXT,
    device_id            TEXT NOT NULL,
    camera_mode          TEXT NOT NULL,
    imu_sample_rate_hz   INTEGER NOT NULL,
    window_size_s        REAL NOT NULL,
    window_hop_s         REAL NOT NULL,
    roi_x                INTEGER,
    roi_y                INTEGER,
    roi_w                INTEGER,
    roi_h                INTEGER,
    model_version        TEXT,
    predicted_state      TEXT,
    confidence_summary   REAL,
    effective_window_count INTEGER DEFAULT 0,
    sync_offset_ms_p95   REAL,
    sync_drift_ppm       REAL,
    aligned_window_ratio REAL,
    error_message        TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(task_status);

CREATE TABLE IF NOT EXISTS window_samples (
    task_id       TEXT NOT NULL,
    window_index  INTEGER NOT NULL,
    payload_json  TEXT NOT NULL,
    PRIMARY KEY (task_id, window_index),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_window_samples_task ON window_samples(task_id, window_index);

-- Legacy offline-import history (renamed from `samples` in v0). Keep as
-- separate concern from live tasks so a stale CSV doesn't pollute the
-- realtime dashboard.
CREATE TABLE IF NOT EXISTS history_samples (
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
CREATE INDEX IF NOT EXISTS idx_history_label ON history_samples(label);
"""


def _resolve_db_path() -> Path:
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_resolve_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)


def fail_orphaned_running_tasks() -> int:
    """Mark any task still in 'running' status as 'failed' on backend startup.

    Backend restarts (intentional or crash) leave the SQLite row in `running`
    even though the in-memory LIVE_STATE is wiped. Without this sweep, the next
    create_task call sees no in-memory active task (so 409 isn't raised) but
    /dashboard/overview happily reports a stale running task. Best to fail
    them explicitly so the operator sees what happened.
    """
    with connect() as conn:
        cursor = conn.execute(
            """
            UPDATE tasks
               SET task_status   = 'failed',
                   finished_at   = COALESCE(finished_at, datetime('now')),
                   error_message = COALESCE(error_message, 'backend restarted while task was running')
             WHERE task_status = 'running'
            """
        )
        return cursor.rowcount


# --------------------------- tasks -----------------------------------------

def insert_task(row: dict[str, Any]) -> None:
    with connect() as conn:
        cols = ", ".join(row.keys())
        placeholders = ", ".join(f":{k}" for k in row.keys())
        conn.execute(f"INSERT INTO tasks ({cols}) VALUES ({placeholders})", row)


def update_task(task_id: str, fields: dict[str, Any]) -> None:
    if not fields:
        return
    assignments = ", ".join(f"{k}=:{k}" for k in fields.keys())
    params = {**fields, "task_id": task_id}
    with connect() as conn:
        conn.execute(f"UPDATE tasks SET {assignments} WHERE task_id=:task_id", params)


def get_task(task_id: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()


def list_tasks(limit: int = 50, offset: int = 0) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ))


def latest_task() -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 1"
        ).fetchone()


def task_success_rate_24h() -> float:
    """Return success / (success + failed) within the last 24h, or 1.0 if no rows."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
              SUM(CASE WHEN task_status = 'succeeded' THEN 1 ELSE 0 END) AS ok,
              SUM(CASE WHEN task_status IN ('succeeded','failed') THEN 1 ELSE 0 END) AS total
            FROM tasks
            WHERE created_at >= datetime('now','-1 day')
            """
        ).fetchone()
        total = (row["total"] or 0) if row else 0
        if total == 0:
            return 1.0
        return float(row["ok"] or 0) / float(total)


# --------------------------- window samples --------------------------------

def insert_window(task_id: str, window_index: int, payload: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO window_samples (task_id, window_index, payload_json)
            VALUES (?, ?, ?)
            """,
            (task_id, window_index, json.dumps(payload)),
        )


def list_windows(task_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT payload_json FROM window_samples WHERE task_id = ? ORDER BY window_index",
            (task_id,),
        ).fetchall()
    return [json.loads(r["payload_json"]) for r in rows]


def get_window(task_id: str, window_index: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM window_samples WHERE task_id = ? AND window_index = ?",
            (task_id, window_index),
        ).fetchone()
    return json.loads(row["payload_json"]) if row else None


# --------------------------- history (offline import) ----------------------

def list_history(
    label: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM history_samples"
    args: list[object] = []
    if label is not None:
        sql += " WHERE label = ?"
        args.append(label)
    sql += " ORDER BY ingested_at DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    with connect() as conn:
        return list(conn.execute(sql, args))


def get_history(sample_id: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM history_samples WHERE sample_id = ?", (sample_id,)
        ).fetchone()


def upsert_history(row: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO history_samples (
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


def delete_history(sample_id: str) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            "DELETE FROM history_samples WHERE sample_id = ?", (sample_id,)
        )
        return cursor.rowcount > 0
