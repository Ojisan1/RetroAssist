"""Mocked thin-UI smoke tests (Phase 7)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from retroassist.app import create_app
from retroassist.config import load_config


def _client(tmp_path: Path) -> TestClient:
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "platform")
    cfg.raw.setdefault("ui", {})["mock_agents"] = True
    return TestClient(create_app(cfg))


def test_health_includes_voice_status(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["voice_status"] == "idle"
        assert payload["mock_ui"] is True


def test_pages_render(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        for path in ("/", "/settings", "/knowledge"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert "RetroAssist" in response.text
            assert "text/html" in response.headers["content-type"]


def test_session_flow_and_export_roundtrip(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        r = client.post(
            "/session/intake",
            data={"symptom": "No power at all.", "notes": "PSU on bench"},
            follow_redirects=False,
        )
        assert r.status_code == 303

        r = client.post("/session/look-now", follow_redirects=False)
        assert r.status_code == 303

        r = client.post(
            "/session/ask",
            data={"query": "What should I check next?"},
            follow_redirects=False,
        )
        assert r.status_code == 303

        home = client.get("/")
        assert "No power at all." in home.text
        assert "Assist:" in home.text or "Suggestions" in home.text

        export = client.get("/session/export")
        assert export.status_code == 200
        body = export.text
        assert "## Intake" in body
        assert "No power at all." in body
        assert "## Suggestions" in body
        assert "attachment" in export.headers.get("content-disposition", "")


def test_preview_jpeg(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/preview.jpg")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content[:2] == b"\xff\xd8"


def test_knowledge_discover_requires_confirm(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        r = client.post(
            "/knowledge/discover",
            data={"platform": "Apple II"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Confirm and import" in r.text
        assert "nothing was ingested yet" in r.text.lower() or "candidate" in r.text.lower()

        # Confirm uses local sample in mock mode
        r2 = client.post(
            "/knowledge/confirm",
            data={"index": "0"},
            follow_redirects=True,
        )
        assert r2.status_code == 200
        assert "Confirmed" in r2.text or "chunk" in r2.text.lower()


def test_settings_saves_speech_mode(tmp_path: Path) -> None:
    platform = tmp_path / "platform"
    cfg = load_config(project_root=tmp_path, platform_dir=platform)
    cfg.raw.setdefault("ui", {})["mock_agents"] = True
    with TestClient(create_app(cfg)) as client:
        r = client.post(
            "/settings",
            data={
                "speech_mode": "open_mic",
                "model_tier": "entry",
                "continuous_fps": "0.5",
                "active_fps": "1.0",
                "mock_agents": "on",
                "camera_device": "",
                "camera_role": "overview",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        saved = (platform / "config.yaml").read_text(encoding="utf-8")
        assert "open_mic" in saved


def test_voice_status_partial(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        r = client.get("/partials/voice-status")
        assert r.status_code == 200
        assert "Voice:" in r.text
