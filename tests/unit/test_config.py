"""Unit tests for configuration merge and paths."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from retroassist.config import (
    deep_merge,
    default_config_dict,
    load_config,
    platform_config_dir,
)


def test_deep_merge_nested_dicts() -> None:
    base = {"a": 1, "nested": {"x": 1, "y": 2}, "list": [1]}
    overlay = {"nested": {"y": 9, "z": 3}, "list": [2, 3], "b": True}
    merged = deep_merge(base, overlay)
    assert merged["a"] == 1
    assert merged["b"] is True
    assert merged["nested"] == {"x": 1, "y": 9, "z": 3}
    assert merged["list"] == [2, 3]
    # originals untouched
    assert base["nested"]["y"] == 2


def test_load_config_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "platform")
    assert cfg.model_tier == "recommended"
    assert cfg.speech_mode == "ptt"
    assert cfg.latency_log_enabled is True
    assert cfg.safety_flags["include_cautionary_framing"] is True
    models = cfg.resolved_models()
    assert models["tier"] == "recommended"
    assert models["llm"]
    assert models["vision"]


def test_platform_then_project_then_env_priority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    platform_dir = tmp_path / "platform"
    platform_dir.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()

    (platform_dir / "config.yaml").write_text(
        yaml.safe_dump({"models": {"tier": "entry"}, "speech": {"mode": "open_mic"}}),
        encoding="utf-8",
    )
    (project_root / "config.yaml").write_text(
        yaml.safe_dump({"models": {"tier": "high_end"}, "models_extra_ignored": True}),
        encoding="utf-8",
    )

    monkeypatch.delenv("RETROASSIST_MODEL_TIER", raising=False)
    monkeypatch.delenv("RETROASSIST_SPEECH_MODE", raising=False)

    cfg = load_config(project_root=project_root, platform_dir=platform_dir)
    assert cfg.model_tier == "high_end"
    assert cfg.speech_mode == "open_mic"

    monkeypatch.setenv("RETROASSIST_MODEL_TIER", "entry")
    monkeypatch.setenv("RETROASSIST_SPEECH_MODE", "ptt")
    cfg2 = load_config(project_root=project_root, platform_dir=platform_dir)
    assert cfg2.model_tier == "entry"
    assert cfg2.speech_mode == "ptt"


def test_explicit_config_path_and_model_overrides(tmp_path: Path) -> None:
    path = tmp_path / "custom.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "models": {
                    "tier": "entry",
                    "llm": "custom-llm",
                    "vision": "custom-vision",
                }
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(
        project_root=tmp_path,
        platform_dir=tmp_path / "empty-platform",
        config_path=path,
    )
    models = cfg.resolved_models()
    assert models["llm"] == "custom-llm"
    assert models["vision"] == "custom-vision"
    assert models["embedding"]  # still from tier profile


def test_invalid_speech_mode_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump({"speech": {"mode": "yelling"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="speech.mode"):
        load_config(project_root=tmp_path, platform_dir=tmp_path / "p", config_path=path)


def test_resolve_data_paths_relative_to_config_dir(tmp_path: Path) -> None:
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "cfg")
    assert cfg.resolve_data_path("sessions") == tmp_path / "cfg" / "sessions"


def test_platform_config_dir_windows_or_posix() -> None:
    path = platform_config_dir()
    assert path.name.lower() in {"retroassist"}
    if os.name == "nt":
        assert "RetroAssist" in str(path) or "retroassist" in str(path).lower()


def test_default_config_dict_has_expected_keys() -> None:
    data = default_config_dict()
    for key in (
        "llm",
        "models",
        "cameras",
        "sampling",
        "data_dirs",
        "speech",
        "safety",
        "latency",
        "vision",
        "rag",
        "agent",
        "server",
    ):
        assert key in data
