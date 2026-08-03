"""Voice dialogue: STT → intent → agent → TTS with latency logging."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from retroassist.agent.loop import DiagnosticAgent
from retroassist.config import AppConfig
from retroassist.interfaces import SpeechToText, TextToSpeech
from retroassist.speech.intents import Intent, parse_intent
from retroassist.speech.modes import MicSource, SpeechModeController
from retroassist.speech.stt import create_stt
from retroassist.speech.tts import create_tts


@dataclass
class VoiceTurnResult:
    transcript: str
    intent: Intent
    suggestion: dict[str, Any] | None
    observation: dict[str, Any] | None
    spoken_text: str
    latency_ms: float
    within_target: bool
    export_path: str | None = None
    audio_chunks: int = 0
    notes: list[str] = field(default_factory=list)


def format_spoken_reply(
    *,
    intent: Intent,
    suggestion: dict[str, Any] | None = None,
    observation: dict[str, Any] | None = None,
    extra: str = "",
) -> str:
    """Compose a short spoken response from agent outputs."""
    if intent is Intent.STOP_SPEAKING:
        return ""
    if intent is Intent.EXPORT_SESSION:
        return extra or "Session exported."
    if intent is Intent.LOOK_NOW and observation:
        summary = str(observation.get("summary") or "I have an updated look at the bench.")
        return f"Looking now. {summary}"
    if suggestion:
        action = str(suggestion.get("action") or "").strip()
        expected = str(suggestion.get("expected_result") or "").strip()
        safety = suggestion.get("safety_notes") or []
        parts = [action]
        if expected:
            parts.append(f"Expect: {expected}")
        if safety:
            parts.append(str(safety[0]))
        return " ".join(p for p in parts if p).strip()
    if extra:
        return extra
    return "Sorry, I did not catch that. Please repeat, or type your question."


class VoiceDialogue:
    """Hands-free turn loop with text fallback always available."""

    def __init__(
        self,
        *,
        agent: DiagnosticAgent,
        stt: SpeechToText,
        tts: TextToSpeech,
        modes: SpeechModeController,
        config: AppConfig | None = None,
        look_now_frames_provider: Any | None = None,
    ) -> None:
        self.agent = agent
        self.stt = stt
        self.tts = tts
        self.modes = modes
        self.config = config
        self.look_now_frames_provider = look_now_frames_provider
        target = 3.0
        if config is not None:
            target = config.voice_turnaround_target_seconds
        self.voice_target_seconds = target
        # Wire barge-in to stop TTS
        self.modes.on_barge_in = self.tts.stop

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        agent: DiagnosticAgent,
        force_mock_speech: bool = False,
        look_now_frames_provider: Any | None = None,
    ) -> VoiceDialogue:
        tts = create_tts(config, force_mock=force_mock_speech)
        modes = SpeechModeController.from_config(config, on_barge_in=tts.stop)
        stt = create_stt(config, force_mock=force_mock_speech)
        return cls(
            agent=agent,
            stt=stt,
            tts=tts,
            modes=modes,
            config=config,
            look_now_frames_provider=look_now_frames_provider,
        )

    async def handle_transcript(self, transcript: str) -> VoiceTurnResult:
        """Process already-known text (typed fallback or mock STT)."""
        started = time.perf_counter()
        intent_result = parse_intent(transcript)
        suggestion: dict[str, Any] | None = None
        observation: dict[str, Any] | None = None
        export_path: str | None = None
        notes: list[str] = []

        if intent_result.intent is Intent.STOP_SPEAKING:
            self.tts.stop()
            notes.append("tts_stopped")
            spoken = ""
        elif intent_result.intent is Intent.EXPORT_SESSION:
            path = self._default_export_path()
            self.agent.export_to_path(str(path))
            export_path = str(path)
            spoken = format_spoken_reply(intent=intent_result.intent, extra=f"Exported to {path}")
        elif intent_result.intent is Intent.LOOK_NOW:
            frames = await self._frames_for_look()
            if frames is None:
                spoken = "I cannot look now; no camera or fixture frames are available."
                notes.append("no_frames")
            else:
                observation = await self.agent.look_now(frames)
                suggestion = await self.agent.suggest_next()
                spoken = format_spoken_reply(
                    intent=intent_result.intent,
                    suggestion=suggestion,
                    observation=observation,
                )
        elif intent_result.intent is Intent.REPORT_MEASUREMENT:
            suggestion = await self.agent.report_measurement(intent_result.payload or transcript)
            spoken = format_spoken_reply(intent=intent_result.intent, suggestion=suggestion)
        elif intent_result.intent is Intent.CLARIFY:
            suggestion = await self.agent.ask(intent_result.payload or transcript)
            spoken = format_spoken_reply(intent=intent_result.intent, suggestion=suggestion)
        else:
            # NEXT_STEP / UNKNOWN→next
            suggestion = await self.agent.ask(intent_result.payload or transcript)
            spoken = format_spoken_reply(intent=Intent.NEXT_STEP, suggestion=suggestion)

        chunks = 0
        if spoken:
            async for _chunk in self.tts.synthesize(spoken):
                chunks += 1
                if self.modes.barge_in_requested:
                    self.tts.stop()
                    notes.append("barge_in")
                    break

        latency_ms = (time.perf_counter() - started) * 1000.0
        within = latency_ms <= (self.voice_target_seconds * 1000.0)
        self._record_latency(latency_ms, within)
        return VoiceTurnResult(
            transcript=transcript,
            intent=intent_result.intent,
            suggestion=suggestion,
            observation=observation,
            spoken_text=spoken,
            latency_ms=latency_ms,
            within_target=within,
            export_path=export_path,
            audio_chunks=chunks,
            notes=notes,
        )

    async def handle_audio(
        self,
        audio: bytes,
        *,
        sample_rate: int | None = None,
    ) -> VoiceTurnResult:
        rate = sample_rate or (
            int(self.config.speech_settings["sample_rate"]) if self.config else 16000
        )
        transcript = (await self.stt.transcribe(audio, sample_rate=rate)).strip()
        if not transcript:
            return VoiceTurnResult(
                transcript="",
                intent=Intent.UNKNOWN,
                suggestion=None,
                observation=None,
                spoken_text="I did not catch that. Please try again, or type your question.",
                latency_ms=0.0,
                within_target=True,
                notes=["empty_transcript"],
            )
        return await self.handle_transcript(transcript)

    async def handle_mic_turn(
        self,
        mic: MicSource,
        *,
        ptt_pressed: bool = True,
    ) -> VoiceTurnResult:
        self.modes.clear_barge_in()
        audio = await self.modes.capture_utterance(mic, ptt_pressed=ptt_pressed)
        if not audio:
            return VoiceTurnResult(
                transcript="",
                intent=Intent.UNKNOWN,
                suggestion=None,
                observation=None,
                spoken_text="",
                latency_ms=0.0,
                within_target=True,
                notes=["no_audio"],
            )
        return await self.handle_audio(audio)

    async def _frames_for_look(self) -> Any | None:
        if self.look_now_frames_provider is None:
            return None
        frames = self.look_now_frames_provider()
        if asyncio_isawaitable(frames):
            frames = await frames  # type: ignore[misc]
        return frames

    def _default_export_path(self) -> Path:
        if self.config is not None:
            base = self.config.resolve_data_path("sessions")
        else:
            base = Path("sessions")
        base.mkdir(parents=True, exist_ok=True)
        return base / f"voice-{self.agent.session.session_id[:8]}.md"

    def _record_latency(self, latency_ms: float, within: bool) -> None:
        self.agent.session.latency_notes.append(
            {
                "timestamp": time.time(),
                "label": "voice_turnaround",
                "latency_ms": latency_ms,
                "target_seconds": self.voice_target_seconds,
                "within_target": within,
            }
        )
        self.agent.session.record(
            "voice_turn",
            {"latency_ms": latency_ms, "within_target": within},
        )


def asyncio_isawaitable(value: Any) -> bool:
    import inspect

    return inspect.isawaitable(value)
