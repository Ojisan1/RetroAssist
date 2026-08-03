"""In-process UI/serve state for the thin web workbench."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from retroassist.agent.loop import DiagnosticAgent
from retroassist.agent.mock_llm import MockAgentLLM
from retroassist.capture.multi_camera import MultiCameraManager
from retroassist.config import AppConfig
from retroassist.paths import fixtures_root, samples_knowledge_root
from retroassist.rag.discovery import DiscoveryCandidate
from retroassist.rag.embeddings import HashingEmbedder
from retroassist.rag.knowledge import LocalKnowledgeStore
from retroassist.vision.analyzer import WorkbenchVisionAnalyzer, frames_from_image_paths
from retroassist.vision.mock_store import MockLLMClient, MockVLMStore

VoiceStatus = Literal["idle", "listening", "thinking", "speaking"]


@dataclass
class ServeState:
    """Shared session + UI status for one ``retroassist serve`` process."""

    config: AppConfig
    agent: DiagnosticAgent
    knowledge: LocalKnowledgeStore
    work_dir: Path
    voice_status: VoiceStatus = "idle"
    discovery_candidates: list[DiscoveryCandidate] = field(default_factory=list)
    cameras: MultiCameraManager | None = None
    fixture_image: Path | None = None
    flash: str | None = None
    mock: bool = True
    transcript_lines: list[str] = field(default_factory=list)

    def set_voice(self, status: VoiceStatus) -> None:
        self.voice_status = status

    def note(self, line: str) -> None:
        self.transcript_lines.append(line)
        if len(self.transcript_lines) > 200:
            self.transcript_lines = self.transcript_lines[-200:]

    def clear_flash(self) -> str | None:
        msg = self.flash
        self.flash = None
        return msg


def _default_fixture_image(config: AppConfig) -> Path | None:
    ui = config.raw.get("ui") or {}
    configured = ui.get("default_fixture_image")
    if configured:
        path = Path(str(configured)).expanduser()
        if path.is_file():
            return path
    try:
        candidate = fixtures_root() / "images" / "power_supply" / "sample.png"
        if candidate.is_file():
            return candidate
    except FileNotFoundError:
        pass
    return None


async def build_serve_state(config: AppConfig, *, mock: bool | None = None) -> ServeState:
    """Construct agent + KB + optional fixture camera for the UI."""
    ui = config.raw.get("ui") or {}
    use_mock = bool(ui.get("mock_agents", True)) if mock is None else bool(mock)
    work_dir = Path(tempfile.mkdtemp(prefix="retroassist-ui-"))
    kb_dir = config.resolve_data_path("knowledge_base") / "chroma"
    kb_dir.parent.mkdir(parents=True, exist_ok=True)

    if use_mock:
        kb = LocalKnowledgeStore(work_dir / "kb", embedder=HashingEmbedder(96))
        # Seed synthetic sample so citations work in demos when samples exist
        try:
            sample = samples_knowledge_root() / "synthetic_psu_notes.md"
            if sample.is_file():
                await kb.ingest(str(sample), metadata={"platform": "sample"})
        except FileNotFoundError:
            pass
        vision = WorkbenchVisionAnalyzer(
            MockLLMClient(MockVLMStore(), case_id="power_supply"),
            model="mock-vlm",
            latency_log_enabled=True,
        )
        agent = DiagnosticAgent(
            llm=MockAgentLLM(case_id="ps01"),
            vision=vision,
            knowledge=kb,
            model="mock-agent",
        )
    else:
        from retroassist.llm.client import LLMClient

        client = LLMClient(
            base_url=config.llm_base_url,
            api_key=config.llm_api_key,
            timeout_seconds=config.llm_timeout_seconds,
        )
        vision = WorkbenchVisionAnalyzer.from_config(config, client)
        kb = LocalKnowledgeStore.from_config(config)
        agent = DiagnosticAgent.from_config(
            config, llm=client, vision=vision, knowledge=kb
        )

    fixture = _default_fixture_image(config)
    cameras: MultiCameraManager | None = None
    configured = config.camera_sources()
    if configured:
        try:
            cameras = MultiCameraManager.from_config(config)
            cameras.open()
        except Exception:  # noqa: BLE001 — UI must start even if cams fail
            cameras = None
    elif fixture is not None:
        cameras = MultiCameraManager.fixture_mode(fixture)
        cameras.open()

    return ServeState(
        config=config,
        agent=agent,
        knowledge=kb,
        work_dir=work_dir,
        cameras=cameras,
        fixture_image=fixture,
        mock=use_mock,
        flash="Mock UI agents active (ci-friendly)." if use_mock else None,
    )


def frames_for_look(state: ServeState) -> list[Any]:
    if state.fixture_image and state.fixture_image.is_file():
        return frames_from_image_paths([str(state.fixture_image)])
    if state.cameras and not state.cameras.zero_camera:
        frames = state.cameras.read_all()
        return list(frames or [])
    return []


def save_settings_overlay(config: AppConfig, overlay: dict[str, Any]) -> Path:
    """Merge overlay into platform config.yaml (thin settings persistence)."""
    import yaml

    from retroassist.config import deep_merge

    path = config.config_dir / "config.yaml"
    config.config_dir.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            existing = loaded
    merged = deep_merge(existing, overlay)
    path.write_text(yaml.safe_dump(merged, sort_keys=False), encoding="utf-8")
    config.raw = deep_merge(config.raw, overlay)
    return path
