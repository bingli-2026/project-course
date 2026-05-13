"""Integration tests for incremental update flow."""

from fastapi.testclient import TestClient

from project_course.api.app import app

client = TestClient(app)


def test_incremental_update_accepts_when_threshold_met() -> None:
    response = client.post(
        "/api/v1/models/incremental-update",
        json={
            "base_model_version": "v0.1.0",
            "new_condition_name": "misaligned",
            "sample_count": 120,
            "session_count": 3,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["update_job_id"].startswith("upd-")


def test_incremental_update_rejects_when_threshold_not_met() -> None:
    response = client.post(
        "/api/v1/models/incremental-update",
        json={
            "base_model_version": "v0.1.0",
            "new_condition_name": "misaligned",
            "sample_count": 10,
            "session_count": 1,
        },
    )
    assert response.status_code == 400
