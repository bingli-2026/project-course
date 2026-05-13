"""Task persistence helpers for experiment task records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class TaskRecord:
    """A lightweight task record for foundational storage wiring."""

    task_id: str
    task_status: str
    created_at: str
    device_id: str


class TaskStore:
    """In-memory foundational store to be replaced by durable backend later."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}

    def create_task(self, task_id: str, device_id: str) -> TaskRecord:
        record = TaskRecord(
            task_id=task_id,
            task_status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            device_id=device_id,
        )
        self._tasks[task_id] = record
        return record

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def update_status(self, task_id: str, status: str) -> TaskRecord | None:
        record = self._tasks.get(task_id)
        if record is None:
            return None
        record.task_status = status
        return record
