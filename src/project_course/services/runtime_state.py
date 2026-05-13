"""Shared in-memory runtime state across API routers."""

from __future__ import annotations

from project_course.services.model_registry import ModelRegistry
from project_course.services.task_store import TaskStore

# Foundational in-memory stores (single process demo scope)
task_store = TaskStore()
model_registry = ModelRegistry()

# Task outputs
task_windows: dict[str, list[dict[str, object]]] = {}
task_results: dict[str, dict[str, object]] = {}

# Incremental update outputs
update_reports: list[dict[str, object]] = []
