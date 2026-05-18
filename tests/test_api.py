"""Tests for the FastAPI application — root, health, and task lifecycle."""

import pytest
from fastapi.testclient import TestClient

from project_course.api import config as config_module
from project_course.api.storage import db


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


def test_task_create_auto_stops_previous_task(client: TestClient) -> None:
    """+ 新建任务 acts as a one-click reset: any running task is force-stopped."""
    first = client.post("/api/v1/tasks", json={"device_id": "rig-test"})
    assert first.status_code == 201
    first_id = first.json()["task_id"]

    second = client.post("/api/v1/tasks", json={"device_id": "rig-test"})
    assert second.status_code == 201
    second_id = second.json()["task_id"]
    assert second_id != first_id

    # The previous task should be marked succeeded (auto-stopped).
    first_detail = client.get(f"/api/v1/tasks/{first_id}").json()
    assert first_detail["task_status"] == "succeeded"
    # The new task should be the active one.
    second_detail = client.get(f"/api/v1/tasks/{second_id}").json()
    assert second_detail["task_status"] == "running"


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


def test_create_task_recovers_from_stale_in_memory_active(client: TestClient) -> None:
    """If SQLite was wiped under a long-running backend, LIVE_STATE.active_task
    may still reference a task that no longer exists. The next create_task
    call should treat the in-memory entry as stale and succeed."""
    from project_course.api.live import LIVE_STATE
    from project_course.api.live.state import LiveTask

    LIVE_STATE.start(
        LiveTask(task_id="task-ghost", device_id="rig-test", window_size_s=0.5, window_hop_s=0.25)
    )
    assert LIVE_STATE.active_task is not None
    # No SQLite row for task-ghost — simulates a wiped DB.

    response = client.post("/api/v1/tasks", json={"device_id": "rig-test"})
    assert response.status_code == 201, response.text
    new_id = response.json()["task_id"]
    assert new_id != "task-ghost"


def test_orphaned_running_task_is_failed_on_startup(tmp_path, monkeypatch) -> None:
    """Startup sweep should fail any task left in `running` state, since the
    in-memory live state can't be resumed across a process restart."""
    monkeypatch.setattr(config_module.settings, "db_path", tmp_path / "test.sqlite3")
    monkeypatch.setattr(config_module.settings, "data_dir", tmp_path / "samples")
    monkeypatch.setattr(config_module.settings, "simulator_enabled", False)
    db.init_db()
    db.insert_task({
        "task_id": "orphan-001", "task_status": "running",
        "created_at": "2026-05-11T10:00:00+00:00",
        "started_at": "2026-05-11T10:00:00+00:00", "finished_at": None,
        "device_id": "rig-x", "camera_mode": "YUY2_160x140_420fps",
        "imu_sample_rate_hz": 1680, "window_size_s": 0.5, "window_hop_s": 0.25,
        "roi_x": None, "roi_y": None, "roi_w": None, "roi_h": None,
        "model_version": None, "predicted_state": None, "confidence_summary": None,
        "effective_window_count": 0,
        "sync_offset_ms_p95": None, "sync_drift_ppm": None, "aligned_window_ratio": None,
        "error_message": None,
    })

    affected = db.fail_orphaned_running_tasks()
    assert affected == 1
    row = db.get_task("orphan-001")
    assert row is not None
    assert row["task_status"] == "failed"
    assert "backend restarted" in (row["error_message"] or "")


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
