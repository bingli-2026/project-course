from __future__ import annotations

from pathlib import Path

from project_course.sensors import ms6dsv_cli


class _FailingReader:
    def __init__(self, **_: object) -> None:
        pass

    def __enter__(self):
        raise OSError("No such device")

    def __exit__(self, *_: object) -> None:
        return None


def test_ms6dsv_cli_soft_fallback_returns_zero(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ms6dsv_cli, "MS6DSVI2CReader", _FailingReader)
    log_path = tmp_path / "ms6dsv.log"
    output = tmp_path / "capture.csv"
    code = ms6dsv_cli.run(
        [
            "--log-path",
            str(log_path),
            "--output",
            str(output),
            "--duration-s",
            "0.1",
        ]
    )
    assert code == 0
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "hardware_unavailable" in content
    assert "soft fallback" in content


def test_ms6dsv_cli_strict_mode_returns_nonzero(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ms6dsv_cli, "MS6DSVI2CReader", _FailingReader)
    code = ms6dsv_cli.run(
        [
            "--strict-hardware",
            "--log-path",
            str(tmp_path / "ms6dsv.log"),
            "--output",
            str(tmp_path / "capture.csv"),
            "--duration-s",
            "0.1",
        ]
    )
    assert code == 2

