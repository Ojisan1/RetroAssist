"""Unit tests for doctor disk / environment checks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from retroassist.config import load_config
from retroassist.doctor import DISK_MIN_FREE_BYTES, DoctorReport, _add_disk_checks


def test_disk_check_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "platform")
    (tmp_path / "platform").mkdir(parents=True, exist_ok=True)

    fake = MagicMock()
    fake.free = DISK_MIN_FREE_BYTES + 100
    fake.total = 100 * 1024**3
    monkeypatch.setattr("retroassist.doctor.shutil.disk_usage", lambda _p: fake)

    report = DoctorReport()
    _add_disk_checks(report, cfg)
    assert len(report.checks) == 1
    assert report.checks[0].name == "disk"
    assert report.checks[0].ok is True
    assert "GiB free" in report.checks[0].detail


def test_disk_check_fails_when_low(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "platform")
    (tmp_path / "platform").mkdir(parents=True, exist_ok=True)

    fake = MagicMock()
    fake.free = DISK_MIN_FREE_BYTES - 1
    fake.total = 10 * 1024**3
    monkeypatch.setattr("retroassist.doctor.shutil.disk_usage", lambda _p: fake)

    report = DoctorReport()
    _add_disk_checks(report, cfg)
    assert report.checks[0].ok is False
    assert "need >=" in report.checks[0].detail
