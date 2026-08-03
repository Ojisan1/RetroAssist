"""Configuration loading, merge, and platform paths."""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from retroassist.llm.models import resolve_model_names

SpeechMode = Literal["ptt", "open_mic"]


def platform_config_dir() -> Path:
    """Return the per-user RetroAssist config directory for this OS."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "RetroAssist"
        return Path.home() / "AppData" / "Roaming" / "RetroAssist"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "retroassist"
    return Path.home() / ".config" / "retroassist"


def default_config_dict() -> dict[str, Any]:
    """Built-in defaults (also mirrored in config.example.yaml)."""
    return {
        "llm": {
            "base_url": "http://127.0.0.1:11434/v1",
            "api_key": "ollama",
            "timeout_seconds": 120,
        },
        "models": {
            "tier": "recommended",
            "llm": None,
            "vision": None,
            "embedding": None,
        },
        "cameras": {
            "sources": [],
            "open_timeout_seconds": 5.0,
            "reconnect_interval_seconds": 2.0,
            "max_reconnect_attempts": 3,
            "enumerate_max_index": 10,
        },
        "sampling": {
            "continuous_fps": 0.4,
            "active_fps": 1.0,
            "change_detection": True,
            "change_threshold": 0.05,
            "on_demand_enabled": True,
            "jpeg_quality": 85,
        },
        "data_dirs": {
            "knowledge_base": "knowledge",
            "sessions": "sessions",
            "cache": "cache",
        },
        "speech": {
            "mode": "ptt",
        },
        "safety": {
            "require_human_confirmation_on_hv": True,
            "include_cautionary_framing": True,
        },
        "latency": {
            "log_enabled": True,
            "look_now_target_seconds": 6.0,
            "voice_turnaround_target_seconds": 3.0,
        },
        "vision": {
            "max_images": 4,
            "jpeg_quality": 85,
        },
        "rag": {
            "embedding_provider": "hashing",  # hashing | ollama
            "embedding_dimensions": 384,
            "chunk_size": 800,
            "chunk_overlap": 100,
            "collection_name": "retroassist_kb",
            "discovery_enabled": True,
            "persist_dir": None,  # default: <knowledge_base>/chroma
        },
        "agent": {
            "require_safety_framing": True,
            "strip_fabricated_citations_when_empty_kb": True,
        },
        "server": {
            "host": "127.0.0.1",
            "port": 8765,
        },
    }


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay onto a copy of base (dicts only; lists replaced)."""
    result = deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config at {path} must be a mapping, got {type(data).__name__}")
    return data


def apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Apply a small set of documented env overrides."""
    result = deepcopy(data)
    if base_url := os.environ.get("RETROASSIST_LLM_BASE_URL"):
        result.setdefault("llm", {})["base_url"] = base_url
    if api_key := os.environ.get("RETROASSIST_LLM_API_KEY"):
        result.setdefault("llm", {})["api_key"] = api_key
    if tier := os.environ.get("RETROASSIST_MODEL_TIER"):
        result.setdefault("models", {})["tier"] = tier
    if mode := os.environ.get("RETROASSIST_SPEECH_MODE"):
        result.setdefault("speech", {})["mode"] = mode
    if host := os.environ.get("RETROASSIST_HOST"):
        result.setdefault("server", {})["host"] = host
    if port := os.environ.get("RETROASSIST_PORT"):
        result.setdefault("server", {})["port"] = int(port)
    return result


@dataclass
class CameraSourceConfig:
    id: str
    device: int | str
    role: str = "overview"


@dataclass
class AppConfig:
    """Resolved RetroAssist configuration."""

    raw: dict[str, Any]
    config_dir: Path
    sources_loaded: list[Path] = field(default_factory=list)

    @property
    def llm_base_url(self) -> str:
        return str(self.raw["llm"]["base_url"])

    @property
    def llm_api_key(self) -> str:
        return str(self.raw["llm"]["api_key"])

    @property
    def llm_timeout_seconds(self) -> float:
        return float(self.raw["llm"]["timeout_seconds"])

    @property
    def model_tier(self) -> str:
        return str(self.raw["models"]["tier"])

    @property
    def speech_mode(self) -> SpeechMode:
        mode = str(self.raw["speech"]["mode"]).strip().lower()
        if mode not in ("ptt", "open_mic"):
            raise ValueError(f"speech.mode must be 'ptt' or 'open_mic', got {mode!r}")
        return mode  # type: ignore[return-value]

    @property
    def latency_log_enabled(self) -> bool:
        return bool(self.raw["latency"]["log_enabled"])

    @property
    def safety_flags(self) -> dict[str, bool]:
        safety = self.raw["safety"]
        return {
            "require_human_confirmation_on_hv": bool(safety["require_human_confirmation_on_hv"]),
            "include_cautionary_framing": bool(safety["include_cautionary_framing"]),
        }

    @property
    def server_host(self) -> str:
        return str(self.raw["server"]["host"])

    @property
    def server_port(self) -> int:
        return int(self.raw["server"]["port"])

    def resolved_models(self) -> dict[str, str]:
        models = self.raw["models"]
        return resolve_model_names(
            str(models["tier"]),
            llm=models.get("llm"),
            vision=models.get("vision"),
            embedding=models.get("embedding"),
        )

    def camera_sources(self) -> list[CameraSourceConfig]:
        cameras = self.raw.get("cameras") or {}
        sources = cameras.get("sources") or []
        result: list[CameraSourceConfig] = []
        for item in sources:
            result.append(
                CameraSourceConfig(
                    id=str(item.get("id", f"cam{len(result)}")),
                    device=item.get("device", 0),
                    role=str(item.get("role", "overview")),
                )
            )
        return result

    def resolve_data_path(self, key: str) -> Path:
        """Resolve a data_dirs entry against the platform config directory."""
        value = Path(str(self.raw["data_dirs"][key]))
        if value.is_absolute():
            return value
        return self.config_dir / value


def load_config(
    *,
    project_root: Path | None = None,
    config_path: Path | None = None,
    platform_dir: Path | None = None,
) -> AppConfig:
    """Load config: defaults ← platform file ← project-local ← explicit path ← env.

    Priority (later wins):
      1. built-in defaults
      2. platform config dir `config.yaml`
      3. project-root `config.yaml` (if project_root given or cwd)
      4. explicit ``config_path``
      5. environment overrides
    """
    config_dir = platform_dir or platform_config_dir()
    merged = default_config_dict()
    sources: list[Path] = []

    platform_file = config_dir / "config.yaml"
    if platform_file.is_file():
        merged = deep_merge(merged, _load_yaml(platform_file))
        sources.append(platform_file)

    root = project_root if project_root is not None else Path.cwd()
    project_file = root / "config.yaml"
    if project_file.is_file() and project_file.resolve() != platform_file.resolve():
        merged = deep_merge(merged, _load_yaml(project_file))
        sources.append(project_file)

    if config_path is not None:
        path = config_path.expanduser().resolve()
        merged = deep_merge(merged, _load_yaml(path))
        sources.append(path)

    merged = apply_env_overrides(merged)
    cfg = AppConfig(raw=merged, config_dir=config_dir, sources_loaded=sources)
    # Validate early
    _ = cfg.speech_mode
    _ = cfg.resolved_models()
    return cfg
