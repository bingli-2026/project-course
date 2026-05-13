"""Contract tests for model versions and incremental update APIs."""

from fastapi.testclient import TestClient

from project_course.api.app import app

client = TestClient(app)


def test_model_versions_contract_shape() -> None:
    response = client.get("/api/v1/models/versions")
    assert response.status_code == 200
    payload = response.json()
    assert "versions" in payload
    assert isinstance(payload["versions"], list)


def test_incremental_update_contract_shape() -> None:
    response = client.post(
        "/api/v1/models/incremental-update",
        json={
            "base_model_version": "v0.1.0",
            "new_condition_name": "loose",
            "sample_count": 120,
            "session_count": 3,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"update_job_id", "status"}
