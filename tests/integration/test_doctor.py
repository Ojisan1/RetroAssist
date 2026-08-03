"""Integration tests for doctor against a mock LLM transport."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from retroassist.capture.base import CameraDeviceInfo
from retroassist.config import load_config
from retroassist.doctor import format_report, run_doctor
from retroassist.llm.client import LLMClient


@pytest.fixture
def mock_cameras(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid opening real VideoCapture devices during doctor tests."""

    def _fake_enumerate(*, max_index: int = 10, probe_frame: bool = True):
        return [CameraDeviceInfo(index=0, name="OBS Virtual Camera", backend="DSHOW")]

    monkeypatch.setattr(
        "retroassist.capture.opencv_source.enumerate_devices",
        _fake_enumerate,
    )

    def _fake_rag(report, cfg) -> None:
        report.add("rag", True, "provider=hashing chunks=0 path=mock")
        report.add("rag.empty", True, "knowledge base empty (mocked)")

    monkeypatch.setattr("retroassist.doctor._add_rag_checks", _fake_rag)


@pytest.mark.asyncio
async def test_doctor_pass_with_mock_llm(tmp_path: Path, mock_cameras: None) -> None:
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "platform")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            models = cfg.resolved_models()
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": models["llm"]},
                        {"id": models["vision"]},
                        {"id": models["embedding"]},
                    ]
                },
            )
        return httpx.Response(404)

    client = LLMClient(base_url="http://mock/v1", transport=httpx.MockTransport(handler))
    report = await run_doctor(cfg, client=client, check_llm=True)
    await client.aclose()

    assert report.ok
    names = {c.name for c in report.checks}
    assert "python" in names
    assert "llm" in names
    assert "models" in names
    assert "disk" in names
    assert "capture" in names
    assert "capture.devices" in names
    text = format_report(report)
    assert "Overall: PASS" in text
    assert "OBS Virtual Camera" in text


@pytest.mark.asyncio
async def test_doctor_fails_when_llm_down(tmp_path: Path, mock_cameras: None) -> None:
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "platform")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    client = LLMClient(base_url="http://mock/v1", transport=httpx.MockTransport(handler))
    report = await run_doctor(cfg, client=client, check_llm=True)
    await client.aclose()

    assert not report.ok
    llm_checks = [c for c in report.checks if c.name == "llm"]
    assert len(llm_checks) == 1
    assert llm_checks[0].ok is False
    assert "Overall: FAIL" in format_report(report)


@pytest.mark.asyncio
async def test_doctor_skip_llm(tmp_path: Path, mock_cameras: None) -> None:
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "platform")
    report = await run_doctor(cfg, check_llm=False)
    assert report.ok
    assert all(c.name != "llm" for c in report.checks)
