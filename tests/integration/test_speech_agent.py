"""Voice transcripts drive the same visual+agent scenarios (no live mic)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from retroassist.agent.loop import DiagnosticAgent
from retroassist.agent.mock_llm import MockAgentLLM
from retroassist.agent.safety import text_implies_high_risk
from retroassist.config import load_config
from retroassist.rag.embeddings import HashingEmbedder
from retroassist.rag.knowledge import LocalKnowledgeStore
from retroassist.speech.dialogue import VoiceDialogue
from retroassist.speech.intents import Intent
from retroassist.speech.modes import SpeechModeController
from retroassist.speech.stt import MockSpeechToText, load_fixture_transcript
from retroassist.speech.tts import MockTextToSpeech
from retroassist.vision.analyzer import WorkbenchVisionAnalyzer, frames_from_image_paths
from retroassist.vision.mock_store import MockLLMClient, MockVLMStore

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "fixtures" / "queries"
IMAGES = ROOT / "fixtures" / "images"
AUDIO = ROOT / "fixtures" / "audio"
VISION_RESP = ROOT / "fixtures" / "vision" / "responses"
AGENT_RESP = ROOT / "fixtures" / "agent" / "responses"
SAMPLES = ROOT.parent / "samples" / "knowledge"

VOICE_CASES = [
    ("ps01", "next_step.json"),
    ("meter01", "measurement.json"),
    ("empty01", "look_now.json"),
    ("nokb01", "next_step.json"),
]


async def _agent_for(case: dict, tmp_path: Path) -> DiagnosticAgent:
    vision = WorkbenchVisionAnalyzer(
        MockLLMClient(MockVLMStore(VISION_RESP), case_id=case["vision_case"]),
        model="mock-vlm",
        latency_log_enabled=False,
    )
    if case.get("use_kb"):
        kb = LocalKnowledgeStore(tmp_path / f"kb-{case['id']}", embedder=HashingEmbedder(96))
        for name in case.get("kb_samples") or []:
            await kb.ingest(str(SAMPLES / name), metadata={"platform": "sample"})
    else:
        kb = LocalKnowledgeStore(tmp_path / f"kb-empty-{case['id']}", embedder=HashingEmbedder(32))
    llm = MockAgentLLM(AGENT_RESP, case_id=case["agent_case"])
    return DiagnosticAgent(llm=llm, vision=vision, knowledge=kb, model="mock-agent")


@pytest.mark.asyncio
@pytest.mark.parametrize(("stem", "audio_sidecar"), VOICE_CASES)
async def test_voice_transcript_scenarios(stem: str, audio_sidecar: str, tmp_path: Path) -> None:
    case = json.loads((QUERIES / f"{stem}.json").read_text(encoding="utf-8"))
    agent = await _agent_for(case, tmp_path)
    await agent.intake(case["symptom"], case.get("visual_notes", ""))

    image = IMAGES / case["image"]
    frames = frames_from_image_paths([str(image)])
    # Seed a look so next_step / measurement have visual context (except look_now case)
    await agent.look_now(frames)

    cfg = load_config(platform_dir=tmp_path / "cfg")
    transcript = load_fixture_transcript(AUDIO / audio_sidecar)
    # Prefer case query for diagnostic asks when sidecar is generic next_step
    if stem in {"ps01", "nokb01"}:
        transcript = case["query"]

    dialogue = VoiceDialogue(
        agent=agent,
        stt=MockSpeechToText(transcript),
        tts=MockTextToSpeech(),
        modes=SpeechModeController(mode="ptt"),
        config=cfg,
        look_now_frames_provider=lambda: frames,
    )

    # Empty-bench case: exercise look_now intent via fixture transcript
    if stem == "empty01":
        result = await dialogue.handle_transcript(transcript)
        assert result.intent is Intent.LOOK_NOW
        assert result.observation is not None
        assert result.observation.get("board_visible") is False
    else:
        wav = (AUDIO / audio_sidecar).with_suffix(".wav")
        # Mock STT returns prepared transcript regardless of WAV contents
        result = await dialogue.handle_audio(wav.read_bytes())

    assert result.spoken_text
    assert result.latency_ms >= 0
    expect = case.get("expect") or {}
    if expect.get("safety_mains") and result.suggestion:
        joined = " ".join(result.suggestion.get("safety_notes") or [])
        assert text_implies_high_risk(joined) or "responsible" in joined.lower()
    if expect.get("kb_empty") and result.suggestion:
        assert result.suggestion.get("kb_empty") is True
        assert result.suggestion.get("citations") == []
    blob = (result.spoken_text + " " + str(result.suggestion)).lower()
    needles = expect.get("must_include_any") or []
    if needles and stem != "empty01":
        assert any(n.lower() in blob for n in needles), blob


@pytest.mark.asyncio
async def test_listen_cli_transcript(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import argparse

    from retroassist.__main__ import _listen_command
    from retroassist.config import load_config

    cfg = load_config(platform_dir=tmp_path / "cfg")
    args = argparse.Namespace(
        mode=None,
        mock=True,
        transcript="What should I check next?",
        audio=None,
        case="ps01",
        agent_case="ps01",
        image=None,
        state=str(tmp_path / "state.json"),
    )
    code = await _listen_command(cfg, args)
    assert code == 0
    out = capsys.readouterr().out.lower()
    assert "intent:" in out
    assert "fuse" in out or "action:" in out
