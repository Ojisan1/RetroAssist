"""Mock STT/TTS and voice dialogue unit coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from retroassist.agent.loop import DiagnosticAgent
from retroassist.agent.mock_llm import MockAgentLLM
from retroassist.config import load_config
from retroassist.speech.dialogue import VoiceDialogue, format_spoken_reply
from retroassist.speech.intents import Intent
from retroassist.speech.modes import SpeechModeController
from retroassist.speech.stt import MockSpeechToText, create_stt, load_fixture_transcript
from retroassist.speech.tts import MockTextToSpeech, create_tts


@pytest.mark.asyncio
async def test_mock_stt_and_tts_roundtrip() -> None:
    stt = MockSpeechToText("What should I check next?")
    text = await stt.transcribe(b"MOCKTRANSCRIPT:Look now")
    assert text == "Look now"
    tts = MockTextToSpeech()
    chunks = [c async for c in tts.synthesize("Check the fuse first.")]
    assert chunks
    assert tts.spoken[-1].startswith("Check the fuse")


def test_create_stt_tts_mock_from_config(tmp_path: Path) -> None:
    cfg = load_config(platform_dir=tmp_path)
    stt = create_stt(cfg, force_mock=True)
    tts = create_tts(cfg, force_mock=True)
    assert isinstance(stt, MockSpeechToText)
    assert isinstance(tts, MockTextToSpeech)


def test_load_audio_fixture_transcript() -> None:
    root = Path(__file__).resolve().parents[1] / "fixtures" / "audio"
    text = load_fixture_transcript(root / "next_step.json")
    assert "check next" in text.lower()


def test_format_spoken_reply_includes_safety() -> None:
    spoken = format_spoken_reply(
        intent=Intent.NEXT_STEP,
        suggestion={
            "action": "Check fuse continuity",
            "expected_result": "Near zero ohms",
            "safety_notes": ["Mains may be present — you remain responsible."],
        },
    )
    assert "fuse" in spoken.lower()
    assert "responsible" in spoken.lower()


@pytest.mark.asyncio
async def test_voice_dialogue_stop_and_export(tmp_path: Path) -> None:
    cfg = load_config(platform_dir=tmp_path / "cfg")
    cfg.raw["data_dirs"]["sessions"] = str(tmp_path / "sessions")
    agent = DiagnosticAgent(llm=MockAgentLLM(case_id="ps01"), model="mock-agent")
    tts = MockTextToSpeech()
    dialogue = VoiceDialogue(
        agent=agent,
        stt=MockSpeechToText(),
        tts=tts,
        modes=SpeechModeController(mode="ptt", on_barge_in=tts.stop),
        config=cfg,
    )
    stop = await dialogue.handle_transcript("Stop speaking")
    assert stop.intent is Intent.STOP_SPEAKING
    assert stop.spoken_text == ""

    exported = await dialogue.handle_transcript("Export the session")
    assert exported.intent is Intent.EXPORT_SESSION
    assert exported.export_path
    assert Path(exported.export_path).is_file()


@pytest.mark.asyncio
async def test_voice_turn_latency_logged(tmp_path: Path) -> None:
    cfg = load_config(platform_dir=tmp_path)
    agent = DiagnosticAgent(llm=MockAgentLLM(case_id="ps01"), model="mock-agent")
    dialogue = VoiceDialogue(
        agent=agent,
        stt=MockSpeechToText(),
        tts=MockTextToSpeech(),
        modes=SpeechModeController(mode="ptt"),
        config=cfg,
    )
    result = await dialogue.handle_transcript("What should I check next?")
    assert result.suggestion
    assert result.latency_ms >= 0
    assert any(n.get("label") == "voice_turnaround" for n in agent.session.latency_notes)
