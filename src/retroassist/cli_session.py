"""Text vertical-slice CLI: intake → look-now → next → export."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from retroassist.agent.loop import DiagnosticAgent
from retroassist.agent.mock_llm import MockAgentLLM
from retroassist.agent.session import DiagnosticSession
from retroassist.config import AppConfig
from retroassist.paths import fixtures_root, samples_knowledge_root
from retroassist.rag.embeddings import HashingEmbedder
from retroassist.rag.knowledge import LocalKnowledgeStore
from retroassist.vision.analyzer import WorkbenchVisionAnalyzer, frames_from_image_paths
from retroassist.vision.mock_store import MockLLMClient, MockVLMStore


@dataclass
class SliceState:
    """Persisted CLI session state (session + how to rebuild mock/live agents)."""

    session: DiagnosticSession = field(default_factory=DiagnosticSession)
    mock: bool = True
    vision_case: str = "power_supply"
    agent_case: str = "ps01"
    empty_kb: bool = False
    kb_samples: list[str] = field(default_factory=list)
    last_query: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session": self.session.to_dict(),
            "meta": {
                "mock": self.mock,
                "vision_case": self.vision_case,
                "agent_case": self.agent_case,
                "empty_kb": self.empty_kb,
                "kb_samples": list(self.kb_samples),
                "last_query": self.last_query,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SliceState:
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        session_raw = data.get("session") if isinstance(data.get("session"), dict) else data
        state = cls(
            session=DiagnosticSession.from_dict(session_raw),
            mock=bool(meta.get("mock", True)),
            vision_case=str(meta.get("vision_case") or "power_supply"),
            agent_case=str(meta.get("agent_case") or "ps01"),
            empty_kb=bool(meta.get("empty_kb", False)),
            kb_samples=[str(x) for x in (meta.get("kb_samples") or [])],
            last_query=str(meta.get("last_query") or ""),
        )
        return state


def default_state_path(config: AppConfig) -> Path:
    return config.resolve_data_path("sessions") / "cli_state.json"


def load_state(path: Path) -> SliceState:
    if not path.is_file():
        return SliceState()
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Session state must be a JSON object: {path}")
    return SliceState.from_dict(data)


def save_state(path: Path, state: SliceState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def load_query_case(stem: str) -> dict[str, Any]:
    path = fixtures_root() / "queries" / f"{stem}.json"
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Query fixture must be an object: {path}")
    return data


async def build_agent_for_state(
    state: SliceState,
    *,
    config: AppConfig,
    work_dir: Path,
) -> DiagnosticAgent:
    """Build a DiagnosticAgent matching slice state (mock CI path or live Ollama)."""
    if state.mock:
        vision = WorkbenchVisionAnalyzer(
            MockLLMClient(MockVLMStore(), case_id=state.vision_case),
            model="mock-vlm",
            latency_target_seconds=float(
                (config.raw.get("latency") or {}).get("look_now_target_seconds", 6.0)
            ),
            latency_log_enabled=bool((config.raw.get("latency") or {}).get("log_enabled", True)),
        )
        kb_dir = work_dir / "kb"
        kb = LocalKnowledgeStore(kb_dir, embedder=HashingEmbedder(96))
        if not state.empty_kb and kb.count == 0 and state.kb_samples:
            samples = samples_knowledge_root()
            for name in state.kb_samples:
                await kb.ingest(str(samples / name), metadata={"platform": "sample"})
        llm = MockAgentLLM(case_id=state.agent_case)
        agent = DiagnosticAgent(
            llm=llm,
            vision=vision,
            knowledge=kb,
            model="mock-agent",
            session=state.session,
            require_safety_framing=bool(
                (config.raw.get("agent") or {}).get("require_safety_framing", True)
            ),
        )
        if state.last_query:
            agent._last_query = state.last_query
        return agent

    from retroassist.llm.client import LLMClient

    client = LLMClient(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        timeout_seconds=config.llm_timeout_seconds,
    )
    vision = WorkbenchVisionAnalyzer.from_config(config, client)
    if state.empty_kb:
        kb = LocalKnowledgeStore(work_dir / "kb-empty", embedder=HashingEmbedder(32))
    else:
        kb = LocalKnowledgeStore.from_config(config)
        if state.kb_samples and kb.count == 0:
            samples = samples_knowledge_root()
            for name in state.kb_samples:
                await kb.ingest(str(samples / name), metadata={"platform": "sample"})
    agent = DiagnosticAgent.from_config(config, llm=client, vision=vision, knowledge=kb)
    agent.session = state.session
    if state.last_query:
        agent._last_query = state.last_query
    return agent


def _format_observation(obs: dict[str, Any]) -> str:
    lines = [
        f"summary: {obs.get('summary', '')}",
        f"board_visible: {obs.get('board_visible')}",
    ]
    if obs.get("meter_reading") is not None:
        lines.append(f"meter_reading: {obs.get('meter_reading')}")
    if obs.get("latency_ms") is not None:
        lines.append(f"latency_ms: {obs.get('latency_ms')}")
        if obs.get("latency_within_target") is not None:
            lines.append(f"within_target: {obs.get('latency_within_target')}")
    return "\n".join(lines)


def _format_suggestion(sug: dict[str, Any]) -> str:
    lines = [
        f"action: {sug.get('action', '')}",
        f"expected_result: {sug.get('expected_result', '')}",
        f"rationale: {sug.get('rationale', '')}",
        f"confidence: {sug.get('confidence', '')}",
        f"kb_empty: {sug.get('kb_empty')}",
    ]
    notes = sug.get("safety_notes") or []
    if notes:
        lines.append("safety_notes:")
        lines.extend(f"  - {n}" for n in notes)
    cites = sug.get("citations") or []
    if cites:
        lines.append("citations:")
        for c in cites:
            lines.append(f"  - {c.get('source')} page={c.get('page')}")
    return "\n".join(lines)


async def cmd_intake(
    state: SliceState,
    *,
    config: AppConfig,
    work_dir: Path,
    symptom: str,
    visual_notes: str = "",
) -> str:
    agent = await build_agent_for_state(state, config=config, work_dir=work_dir)
    await agent.intake(symptom, visual_notes)
    state.session = agent.session
    return f"Intake recorded: {symptom}"


async def cmd_look_now(
    state: SliceState,
    *,
    config: AppConfig,
    work_dir: Path,
    image: Path,
) -> str:
    if not image.is_file():
        raise FileNotFoundError(f"Image not found: {image}")
    agent = await build_agent_for_state(state, config=config, work_dir=work_dir)
    frames = frames_from_image_paths([str(image)])
    if not frames:
        raise RuntimeError(f"Could not load image frames from {image}")
    obs = await agent.look_now(frames)
    state.session = agent.session
    return _format_observation(obs)


async def cmd_next(
    state: SliceState,
    *,
    config: AppConfig,
    work_dir: Path,
    query: str | None = None,
) -> str:
    agent = await build_agent_for_state(state, config=config, work_dir=work_dir)
    if query:
        sug = await agent.ask(query)
        state.last_query = query
    else:
        sug = await agent.suggest_next()
    state.session = agent.session
    state.last_query = agent._last_query
    return _format_suggestion(sug)


def cmd_export(state: SliceState, *, out: Path) -> str:
    from retroassist.agent.export import export_session_markdown

    path = export_session_markdown(state.session, out)
    return f"Exported session markdown to {path}"


async def cmd_run(
    *,
    config: AppConfig,
    work_dir: Path,
    symptom: str,
    visual_notes: str,
    image: Path,
    query: str,
    export_path: Path,
    mock: bool,
    vision_case: str,
    agent_case: str,
    empty_kb: bool,
    kb_samples: list[str],
) -> str:
    """One-shot text slice: intake → look-now → ask → export."""
    state = SliceState(
        mock=mock,
        vision_case=vision_case,
        agent_case=agent_case,
        empty_kb=empty_kb,
        kb_samples=kb_samples,
    )
    await cmd_intake(
        state, config=config, work_dir=work_dir, symptom=symptom, visual_notes=visual_notes
    )
    obs_text = await cmd_look_now(state, config=config, work_dir=work_dir, image=image)
    sug_text = await cmd_next(state, config=config, work_dir=work_dir, query=query)
    export_msg = cmd_export(state, out=export_path)
    return "\n\n".join(
        [
            "## Intake",
            f"symptom: {symptom}",
            f"visual_notes: {visual_notes or '(none)'}",
            "",
            "## Look now",
            obs_text,
            "",
            "## Next step",
            sug_text,
            "",
            "## Export",
            export_msg,
            "",
            f"session_id: {state.session.session_id}",
            f"latency_notes: {json.dumps(state.session.latency_notes, default=str)}",
        ]
    )


async def cmd_run_from_case(
    *,
    config: AppConfig,
    work_dir: Path,
    case_stem: str,
    export_path: Path,
    mock: bool = True,
) -> str:
    """Run the full text slice using a query fixture (e.g. ps01)."""
    case = load_query_case(case_stem)
    image = fixtures_root() / "images" / case["image"]
    kb_samples = [str(x) for x in (case.get("kb_samples") or [])]
    empty_kb = not bool(case.get("use_kb"))
    return await cmd_run(
        config=config,
        work_dir=work_dir,
        symptom=str(case["symptom"]),
        visual_notes=str(case.get("visual_notes") or ""),
        image=image,
        query=str(case["query"]),
        export_path=export_path,
        mock=mock,
        vision_case=str(case.get("vision_case") or case_stem),
        agent_case=str(case.get("agent_case") or case_stem),
        empty_kb=empty_kb,
        kb_samples=kb_samples,
    )
