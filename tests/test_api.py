"""Tests for the FastAPI application."""

from fastapi.testclient import TestClient

from project_course.api.app import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "project-course api"}


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
