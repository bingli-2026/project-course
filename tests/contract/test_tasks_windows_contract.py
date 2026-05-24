"""Contract tests for task windows and spectra APIs."""

from fastapi.testclient import TestClient

from project_course.api import config as config_module


def test_windows_and_spectra_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config_module.settings, "db_path", tmp_path / "test.sqlite3")
    monkeypatch.setattr(config_module.settings, "data_dir", tmp_path / "samples")
    monkeypatch.setattr(config_module.settings, "simulator_enabled", False)
    monkeypatch.setattr(config_module.settings, "capture_on_create", True)

    from project_course.api.app import create_app

    with TestClient(create_app()) as client:
        create = client.post("/api/v1/tasks", json={"device_id": "rig-01"})
        assert create.status_code == 201
        task_id = create.json()["task_id"]

        windows = client.get(f"/api/v1/tasks/{task_id}/windows")
        assert windows.status_code == 200
        payload = windows.json()
        assert payload["task_id"] == task_id
        assert isinstance(payload["samples"], list)

        first = payload["samples"][0]
        required = {
            "sample_id",
            "window_index",
            "center_time_s",
            "vision_dx_peak_hz",
            "sensor_ax_peak_hz",
            "fused_dominant_freq_hz",
        }
        assert required.issubset(first.keys())

        spectra = client.get(
            f"/api/v1/tasks/{task_id}/spectra", params={"window_index": 0}
        )
        assert spectra.status_code == 200
        s_payload = spectra.json()
        assert "sensor_ax" in s_payload
        assert "vision_dx" in s_payload
