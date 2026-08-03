"""FastAPI app smoke tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from retroassist.app import create_app
from retroassist.config import load_config


def test_health_endpoint(tmp_path: Path) -> None:
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "platform")
    with TestClient(create_app(cfg)) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["speech_mode"] == "ptt"
        assert payload["model_tier"] == "recommended"
