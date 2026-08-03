"""Keyframe + query agent integration suite (mocked vision + agent LLM)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from retroassist.agent.loop import DiagnosticAgent
from retroassist.agent.mock_llm import MockAgentLLM
from retroassist.agent.safety import rejects_fabricated_manual_citation, text_implies_high_risk
from retroassist.rag.embeddings import HashingEmbedder
from retroassist.rag.knowledge import LocalKnowledgeStore
from retroassist.vision.analyzer import WorkbenchVisionAnalyzer, frames_from_image_paths
from retroassist.vision.mock_store import MockLLMClient, MockVLMStore

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "fixtures" / "images"
QUERIES = ROOT / "fixtures" / "queries"
VISION_RESP = ROOT / "fixtures" / "vision" / "responses"
AGENT_RESP = ROOT / "fixtures" / "agent" / "responses"
SAMPLES = ROOT.parent / "samples" / "knowledge"

CASES = ["ps01", "ps02", "logic01", "meter01", "empty01", "nokb01"]


def _load_query(stem: str) -> dict:
    with (QUERIES / f"{stem}.json").open(encoding="utf-8") as handle:
        return json.load(handle)


async def _build_agent(case: dict, tmp_path: Path) -> DiagnosticAgent:
    vision_client = MockLLMClient(MockVLMStore(VISION_RESP), case_id=case["vision_case"])
    vision = WorkbenchVisionAnalyzer(
        vision_client,
        model="mock-vlm",
        latency_log_enabled=False,
    )
    kb: LocalKnowledgeStore | None
    if case.get("use_kb"):
        kb = LocalKnowledgeStore(tmp_path / f"kb-{case['id']}", embedder=HashingEmbedder(96))
        for name in case.get("kb_samples") or []:
            await kb.ingest(str(SAMPLES / name), metadata={"platform": "sample"})
    else:
        kb = LocalKnowledgeStore(tmp_path / f"kb-empty-{case['id']}", embedder=HashingEmbedder(32))
        assert kb.count == 0

    agent_llm = MockAgentLLM(AGENT_RESP, case_id=case["agent_case"])
    return DiagnosticAgent(llm=agent_llm, vision=vision, knowledge=kb, model="mock-agent")


def _blob(suggestion: dict, observation: dict) -> str:
    parts = [
        suggestion.get("action", ""),
        suggestion.get("expected_result", ""),
        suggestion.get("rationale", ""),
        " ".join(suggestion.get("safety_notes") or []),
        observation.get("summary", ""),
        str(observation.get("meter_reading") or ""),
    ]
    return " ".join(parts).lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("stem", CASES)
async def test_keyframe_agent_cases(stem: str, tmp_path: Path) -> None:
    case = _load_query(stem)
    agent = await _build_agent(case, tmp_path)
    await agent.intake(case["symptom"], case.get("visual_notes", ""))

    image = IMAGES / case["image"]
    assert image.is_file(), image
    frames = frames_from_image_paths([str(image)])
    observation = await agent.look_now(frames)
    suggestion = await agent.ask(case["query"])
    expect = case["expect"]

    blob = _blob(suggestion, observation)
    needles = expect.get("must_include_any") or []
    assert any(n.lower() in blob for n in needles), (
        f"{case['id']} missing any of {needles} in {blob!r}"
    )

    if expect.get("board_visible") is False:
        assert observation.get("board_visible") is False

    if expect.get("acknowledge_meter"):
        assert observation.get("meter_reading") or "0.00" in blob or "zero" in blob

    if expect.get("safety_mains"):
        joined_safety = " ".join(suggestion.get("safety_notes") or [])
        assert text_implies_high_risk(joined_safety) or "responsible" in joined_safety.lower()

    if expect.get("citations_required"):
        assert suggestion.get("citations"), f"{case['id']} expected citations"

    if expect.get("kb_empty") or expect.get("no_fabricated_citations"):
        assert suggestion.get("kb_empty") is True
        assert suggestion.get("citations") == []
        for key in ("action", "rationale", "expected_result"):
            assert not rejects_fabricated_manual_citation(str(suggestion.get(key) or ""))

    md = agent.export_markdown()
    assert case["symptom"] in md
    assert "## Suggestions" in md
    assert observation.get("summary", "")[:20] in md or "Observation" in md
