"""Integration tests for task capture pipeline."""

from fastapi.testclient import TestClient

from project_course.api import config as config_module


def test_create_task_runs_pipeline_and_returns_windows(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config_module.settings, "db_path", tmp_path / "test.sqlite3")
    monkeypatch.setattr(config_module.settings, "data_dir", tmp_path / "samples")
    monkeypatch.setattr(config_module.settings, "simulator_enabled", False)
    monkeypatch.setattr(config_module.settings, "capture_on_create", True)

    from project_course.api.app import create_app

    with TestClient(create_app()) as client:
        create = client.post(
            "/api/v1/tasks",
            json={"device_id": "rig-01", "window_size_s": 0.25, "window_hop_s": 0.05},
        )
        assert create.status_code == 201
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
