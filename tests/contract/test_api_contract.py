"""Contract skeleton tests for foundational API routes."""

from fastapi.testclient import TestClient

from project_course.api.app import app

client = TestClient(app)


def test_health_route_exists() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_tasks_route_exists() -> None:
    response = client.get("/api/v1/tasks/task-placeholder")
    assert response.status_code == 200


def test_dashboard_route_exists() -> None:
    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 200
