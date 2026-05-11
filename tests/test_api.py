"""Tests for the FastAPI application — root, health, and task lifecycle."""

import pytest
from fastapi.testclient import TestClient

from project_course.api import config as config_module


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    # Isolate SQLite and disable the background simulator so tests stay deterministic.
    monkeypatch.setattr(config_module.settings, "db_path", tmp_path / "test.sqlite3")
    monkeypatch.setattr(config_module.settings, "data_dir", tmp_path / "samples")
    monkeypatch.setattr(config_module.settings, "simulator_enabled", False)

    from project_course.api.app import create_app
    from project_course.api.live import finish_task, get_active_task

    with TestClient(create_app()) as c:
        yield c

    if get_active_task() is not None:
        finish_task(status="succeeded")


def test_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "project-course api"}


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_history_list_empty(client: TestClient) -> None:
    response = client.get("/api/v1/history")
    assert response.status_code == 200
    assert response.json() == []


def test_history_get_missing(client: TestClient) -> None:
    response = client.get("/api/v1/history/does-not-exist")
    assert response.status_code == 404


def test_task_create_and_get(client: TestClient) -> None:
    create = client.post("/api/v1/tasks", json={"device_id": "rig-test"})
    assert create.status_code == 201, create.text
    task_id = create.json()["task_id"]
    assert create.json()["task_status"] == "running"

    detail = client.get(f"/api/v1/tasks/{task_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["task_id"] == task_id
    assert body["device_id"] == "rig-test"
    assert body["window_size_s"] == 0.5
    assert body["window_hop_s"] == 0.25

    # Stop the task so the next test isn't blocked by 409.
    stop = client.post(f"/api/v1/tasks/{task_id}/stop")
    assert stop.status_code == 200
    assert stop.json()["task_status"] == "succeeded"


def test_task_create_conflict_when_already_running(client: TestClient) -> None:
    first = client.post("/api/v1/tasks", json={"device_id": "rig-test"})
    assert first.status_code == 201
    second = client.post("/api/v1/tasks", json={"device_id": "rig-test"})
    assert second.status_code == 409


def test_task_windows_after_publish(client: TestClient) -> None:
    from project_course.api.live import publish_window

    create = client.post("/api/v1/tasks", json={"device_id": "rig-test"})
    task_id = create.json()["task_id"]
    publish_window(
        {
            "sample_id": task_id,
            "window_index": 0,
            "center_time_s": 0.25,
            "vision_dx_peak_hz": 12.0,
            "sensor_ax_peak_hz": 50.0,
            "predicted_state": "normal",
            "prediction_confidence": 0.9,
        }
    )

    windows = client.get(f"/api/v1/tasks/{task_id}/windows")
    assert windows.status_code == 200
    samples = windows.json()["samples"]
    assert len(samples) == 1
    assert samples[0]["window_index"] == 0
    assert samples[0]["vision_dx_peak_hz"] == 12.0

    detail = client.get(f"/api/v1/tasks/{task_id}").json()
    assert detail["predicted_state"] == "normal"
    assert detail["confidence_summary"] == pytest.approx(0.9)


def test_task_spectra_returns_curves(client: TestClient) -> None:
    from project_course.api.live import publish_window

    create = client.post("/api/v1/tasks", json={"device_id": "rig-test"})
    task_id = create.json()["task_id"]
    publish_window(
        {
            "sample_id": task_id,
            "window_index": 0,
            "center_time_s": 0.25,
            "vision_dx_peak_hz": 12.0,
            "vision_dx_peak_power": 0.5,
            "sensor_ax_peak_hz": 50.0,
            "sensor_ax_peak_power": 0.8,
        }
    )

    spectra = client.get(
        f"/api/v1/tasks/{task_id}/spectra", params={"window_index": 0}
    )
    assert spectra.status_code == 200
    body = spectra.json()
    assert body["window_index"] == 0
    assert body["vision_dx"] is not None
    assert len(body["vision_dx"]["freq_hz"]) > 0
    assert body["sensor_ax"] is not None


def test_dashboard_overview_when_idle(client: TestClient) -> None:
    overview = client.get("/api/v1/dashboard/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert body["latest_task_id"] is None
    assert body["task_success_rate_24h"] == 1.0


def test_dashboard_overview_reflects_active_task(client: TestClient) -> None:
    from project_course.api.live import publish_window

    create = client.post("/api/v1/tasks", json={"device_id": "rig-test"})
    task_id = create.json()["task_id"]
    publish_window(
        {
            "sample_id": task_id,
            "window_index": 0,
            "center_time_s": 0.25,
            "fused_dominant_freq_hz": 31.5,
            "predicted_state": "unbalance",
            "prediction_confidence": 0.91,
        }
    )

    overview = client.get("/api/v1/dashboard/overview").json()
    assert overview["latest_task_id"] == task_id
    assert overview["latest_status"] == "running"
    assert overview["latest_predicted_state"] == "unbalance"
    assert overview["latest_fused_frequency_hz"] == pytest.approx(31.5)
    assert overview["latest_window_index"] == 0
