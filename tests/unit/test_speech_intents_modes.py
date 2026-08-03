"""Intent parsing and speech mode unit tests."""

from __future__ import annotations

import struct

import numpy as np
import pytest

from retroassist.speech.intents import Intent, parse_intent
from retroassist.speech.modes import MockMicSource, SpeechModeController, pcm_rms_energy
from retroassist.speech.tts import MockTextToSpeech


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Look now please", Intent.LOOK_NOW),
        ("What do you see on the bench?", Intent.LOOK_NOW),
        ("What should I check next?", Intent.NEXT_STEP),
        ("Next step please", Intent.NEXT_STEP),
        ("I'm measuring 4.2 volts on that pin", Intent.REPORT_MEASUREMENT),
        ("Reading zero on the 12V rail", Intent.REPORT_MEASUREMENT),
        ("Can you clarify that?", Intent.CLARIFY),
        ("Is that within range?", Intent.CLARIFY),
        ("Stop speaking", Intent.STOP_SPEAKING),
        ("Export the session", Intent.EXPORT_SESSION),
        ("Help me with the regulator", Intent.NEXT_STEP),
    ],
)
def test_parse_intent(text: str, expected: Intent) -> None:
    assert parse_intent(text).intent is expected


def test_pcm_rms_detects_tone() -> None:
    silence = b"\x00\x00" * 160
    assert pcm_rms_energy(silence) < 0.001
    tone = b"".join(struct.pack("<h", int(12000 * np.sin(i / 10))) for i in range(320))
    assert pcm_rms_energy(tone) > 0.1


@pytest.mark.asyncio
async def test_ptt_captures_stream() -> None:
    chunk = b"\x10\x00" * 160
    mic = MockMicSource([chunk, chunk, chunk], trailing_silence_chunks=1)
    ctl = SpeechModeController(mode="ptt", ptt_max_seconds=2.0)
    audio = await ctl.capture_utterance(mic, ptt_pressed=True)
    assert len(audio) >= len(chunk)


@pytest.mark.asyncio
async def test_open_mic_vad_endpoint() -> None:
    silence = b"\x00\x00" * 160
    tone = b"".join(struct.pack("<h", 20000 if (i % 2 == 0) else -20000) for i in range(160))
    # speech then silence → endpoint
    mic = MockMicSource(
        [tone, tone, tone, silence, silence, silence, silence, silence, silence],
        trailing_silence_chunks=0,
    )
    ctl = SpeechModeController(
        mode="open_mic",
        vad_energy_threshold=0.05,
        vad_silence_ms=90,  # ~3 chunks at 30ms
        vad_min_speech_ms=30,
        open_mic_max_seconds=5.0,
    )
    audio = await ctl.capture_utterance(mic)
    assert len(audio) > 0
    assert ctl.barge_in_requested is True


@pytest.mark.asyncio
async def test_barge_in_stops_tts() -> None:
    tts = MockTextToSpeech()
    ctl = SpeechModeController(mode="open_mic", on_barge_in=tts.stop)
    # Start synthesis concurrently-ish then barge-in
    gen = tts.synthesize("hello technician")
    first = await gen.__anext__()
    assert first
    ctl.request_barge_in()
    assert tts.speaking is False
    # Remaining chunks should stop early
    remaining = []
    async for chunk in gen:
        remaining.append(chunk)
    assert tts.chunks_emitted <= 3


def test_mode_switch() -> None:
    ctl = SpeechModeController(mode="ptt")
    ctl.set_mode("open_mic")
    assert ctl.mode == "open_mic"
    with pytest.raises(ValueError):
        ctl.set_mode("yelling")  # type: ignore[arg-type]
