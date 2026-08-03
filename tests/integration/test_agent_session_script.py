"""Multi-turn scripted session fixture test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from retroassist.agent.loop import DiagnosticAgent
from retroassist.agent.mock_llm import MockAgentLLM
from retroassist.rag.embeddings import HashingEmbedder
from retroassist.rag.knowledge import LocalKnowledgeStore
from retroassist.vision.analyzer import WorkbenchVisionAnalyzer, frames_from_image_paths
from retroassist.vision.mock_store import MockLLMClient, MockVLMStore

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "fixtures" / "sessions" / "psu_no_power.json"
IMAGES = ROOT / "fixtures" / "images"
VISION_RESP = ROOT / "fixtures" / "vision" / "responses"
AGENT_RESP = ROOT / "fixtures" / "agent" / "responses"
SAMPLES = ROOT.parent / "samples" / "knowledge"


@pytest.mark.asyncio
async def test_psu_no_power_session_script(tmp_path: Path) -> None:
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    kb = LocalKnowledgeStore(tmp_path / "kb", embedder=HashingEmbedder(96))
    await kb.ingest(str(SAMPLES / "synthetic_psu_notes.md"), metadata={"platform": "psu"})

    vision = WorkbenchVisionAnalyzer(
        MockLLMClient(MockVLMStore(VISION_RESP), case_id="power_supply"),
        model="mock-vlm",
        latency_log_enabled=False,
    )
    agent_llm = MockAgentLLM(AGENT_RESP, case_id="ps01")
    agent = DiagnosticAgent(llm=agent_llm, vision=vision, knowledge=kb)

    for step in script["steps"]:
        op = step["op"]
        if op == "intake":
            await agent.intake(step["symptom"], step.get("visual_notes", ""))
        elif op == "look_now":
            frames = frames_from_image_paths([str(IMAGES / step["image"])])
            await agent.look_now(frames)
        elif op == "ask":
            agent_llm.set_case(step["agent_case"])
            await agent.ask(step["query"])
        elif op == "report_measurement":
            agent_llm.set_case(step["agent_case"])
            await agent.report_measurement(step["text"])
        else:
            raise AssertionError(f"unknown op {op}")

    assert agent.session.intake is not None
    assert agent.session.observations
    assert len(agent.session.suggestions) >= 2
    assert agent.session.measurements
    assert agent.session.steps_tried
    md = agent.export_markdown()
    assert "No power" in md
    assert "Fuse reads open" in md
    assert "## Event log" in md
