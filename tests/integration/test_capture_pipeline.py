"""Integration tests for task capture pipeline."""

from fastapi.testclient import TestClient

from project_course.api.app import app

client = TestClient(app)


def test_create_task_runs_pipeline_and_returns_windows() -> None:
    create = client.post(
        "/api/v1/tasks",
        json={"device_id": "rig-01", "window_size_s": 0.25, "window_hop_s": 0.05},
    )
    assert create.status_code == 200
    task_id = create.json()["task_id"]

    detail = client.get(f"/api/v1/tasks/{task_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["task_status"] == "succeeded"
    assert payload["effective_window_count"] > 0

    windows = client.get(f"/api/v1/tasks/{task_id}/windows")
    assert windows.status_code == 200
    samples = windows.json()["samples"]
    assert len(samples) > 0
    assert "sensor_ax_peak_hz" in samples[0]
    assert "vision_dx_peak_hz" in samples[0]
