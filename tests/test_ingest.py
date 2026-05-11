"""Tests for the feature-file ingest pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from project_course.api import config as config_module
from project_course.api.storage import db
from project_course.api.storage.ingest import (
    IngestValidationError,
    ingest_file,
    scan_directory,
)


def _vision_row(sample_id: str, window_index: int, t: float, label: str = "normal") -> dict:
    return {
        "sample_id": sample_id,
        "label": label,
        "modality": "vision",
        "source_name": f"{sample_id}.mp4",
        "window_index": window_index,
        "window_start_frame": window_index * 100,
        "window_end_frame": (window_index + 1) * 100,
        "center_time_s": t,
        "analysis_fps": 420.0,
        "vision_dx_peak_hz": 12.5 + window_index * 0.1,
        "vision_dy_peak_hz": 14.0 + window_index * 0.1,
        "vision_dx_peak_power": 0.85,
        "vision_dy_peak_power": 0.71,
    }


@pytest.fixture
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "samples"
    data_dir.mkdir()
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(config_module.settings, "data_dir", data_dir)
    monkeypatch.setattr(config_module.settings, "db_path", db_path)
    db.init_db()
    return data_dir


def test_ingest_valid_csv(isolated_data_dir: Path) -> None:
    df = pd.DataFrame([_vision_row("s001", i, i * 0.5) for i in range(4)])
    csv_path = isolated_data_dir / "s001.csv"
    df.to_csv(csv_path, index=False)

    result = ingest_file(csv_path)

    assert result.sample_id == "s001"
    assert result.window_count == 4
    assert result.has_vision is True
    assert result.has_sensor is False
    assert result.label == "normal"

    row = db.get_sample("s001")
    assert row is not None
    assert row["window_count"] == 4
    assert row["has_vision"] == 1


def test_ingest_missing_columns(isolated_data_dir: Path) -> None:
    df = pd.DataFrame([{"sample_id": "s002", "center_time_s": 0.0}])
    csv_path = isolated_data_dir / "s002.csv"
    df.to_csv(csv_path, index=False)

    with pytest.raises(IngestValidationError) as exc_info:
        ingest_file(csv_path)

    assert "window_index" in exc_info.value.missing_columns


def test_ingest_rejects_multiple_sample_ids(isolated_data_dir: Path) -> None:
    rows = [_vision_row("a", 0, 0.0), _vision_row("b", 1, 0.5)]
    csv_path = isolated_data_dir / "mixed.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    with pytest.raises(IngestValidationError):
        ingest_file(csv_path)


def test_scan_directory_skips_invalid_files(isolated_data_dir: Path) -> None:
    good = pd.DataFrame([_vision_row("good", i, i * 0.5) for i in range(3)])
    good.to_csv(isolated_data_dir / "good.csv", index=False)

    bad = pd.DataFrame([{"foo": "bar"}])
    bad.to_csv(isolated_data_dir / "bad.csv", index=False)

    (isolated_data_dir / "ignored.txt").write_text("not a feature file")

    results = scan_directory()

    assert {r.sample_id for r in results} == {"good"}
    assert db.get_sample("good") is not None


def test_upload_endpoint_round_trip(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    df = pd.DataFrame([_vision_row("up001", i, i * 0.25) for i in range(2)])
    csv_path = isolated_data_dir.parent / "upload.csv"
    df.to_csv(csv_path, index=False)

    from project_course.api.app import create_app

    with TestClient(create_app()) as client:
        with csv_path.open("rb") as fh:
            response = client.post(
                "/api/v1/samples",
                files={"file": ("up001.csv", fh, "text/csv")},
            )
        assert response.status_code == 201, response.text
        meta = response.json()
        assert meta["sample_id"] == "up001"
        assert meta["window_count"] == 2
        assert meta["has_vision"] is True

        listing = client.get("/api/v1/samples").json()
        assert any(s["sample_id"] == "up001" for s in listing)

        delete_response = client.delete("/api/v1/samples/up001")
        assert delete_response.status_code == 204
        assert client.get("/api/v1/samples/up001").status_code == 404
        assert not (isolated_data_dir / "up001.csv").exists()


def test_upload_endpoint_rejects_invalid_schema(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_path = isolated_data_dir.parent / "bad.csv"
    pd.DataFrame([{"sample_id": "x", "center_time_s": 0.0}]).to_csv(bad_path, index=False)

    from project_course.api.app import create_app

    with TestClient(create_app()) as client:
        with bad_path.open("rb") as fh:
            response = client.post(
                "/api/v1/samples",
                files={"file": ("bad.csv", fh, "text/csv")},
            )
        assert response.status_code == 422
        body = response.json()
        assert "window_index" in body["detail"]["missing_columns"]
        # The rejected file should not have leaked into the data dir
        assert not (isolated_data_dir / "bad.csv").exists()


def test_get_sample_endpoint_returns_rows(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    df = pd.DataFrame([_vision_row("ep001", i, i * 0.5) for i in range(3)])
    df.to_csv(isolated_data_dir / "ep001.csv", index=False)
    scan_directory()

    from project_course.api.app import create_app

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/samples/ep001")
        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["sample_id"] == "ep001"
        assert len(body["rows"]) == 3
        assert body["rows"][0]["vision_dx_peak_hz"] == pytest.approx(12.5, abs=1e-6)

        ts = client.get(
            "/api/v1/samples/ep001/timeseries",
            params={"fields": ["vision_dx_peak_hz", "vision_dy_peak_hz"]},
        )
        assert ts.status_code == 200
        ts_body = ts.json()
        assert ts_body["fields"] == ["vision_dx_peak_hz", "vision_dy_peak_hz"]
        assert len(ts_body["points"]) == 3
        assert ts_body["points"][0]["center_time_s"] == 0.0
