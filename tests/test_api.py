"""Tests for the FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from project_course.api.app import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "project-course api"}


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_samples_list_empty(client: TestClient) -> None:
    response = client.get("/api/v1/samples")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_samples_get_missing(client: TestClient) -> None:
    response = client.get("/api/v1/samples/does-not-exist")
    assert response.status_code == 404
