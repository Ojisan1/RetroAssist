"""Text-to-speech: mock (CI) and Piper (local binary)."""

from __future__ import annotations

import asyncio
import io
import wave
from collections.abc import AsyncIterator
from pathlib import Path

from retroassist.config import AppConfig
from retroassist.interfaces import TextToSpeech


class TTSError(Exception):
    """TTS failure."""


class MockTextToSpeech(TextToSpeech):
    """CI-safe TTS: yields a tiny silent WAV and honors ``stop()`` / barge-in."""

    def __init__(self, *, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self._speaking = False
        self._stop = False
        self.spoken: list[str] = []
        self.chunks_emitted = 0

    @property
    def speaking(self) -> bool:
        return self._speaking

    def stop(self) -> None:
        self._stop = True
        self._speaking = False

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        self._stop = False
        self._speaking = True
        self.spoken.append(text)
        # Three tiny silent frames so barge-in can be observed mid-stream
        frame = _silent_wav_chunk(sample_rate=self.sample_rate, duration_ms=20)
        try:
            for _ in range(3):
                if self._stop:
                    break
                self.chunks_emitted += 1
                yield frame
                await asyncio.sleep(0)
        finally:
            self._speaking = False


class PiperTextToSpeech(TextToSpeech):
    """Local Piper TTS via CLI (``piper`` binary + ``.onnx`` voice model)."""

    def __init__(
        self,
        *,
        binary: str = "piper",
        voice_model: str | Path | None = None,
        sample_rate: int = 22050,
    ) -> None:
        if not voice_model:
            raise TTSError(
                "speech.piper_voice_model path is required when tts_provider=piper"
            )
        self.binary = binary
        self.voice_model = Path(voice_model)
        self.sample_rate = sample_rate
        self._speaking = False
        self._stop = False
        self._proc: asyncio.subprocess.Process | None = None

    @property
    def speaking(self) -> bool:
        return self._speaking

    def stop(self) -> None:
        self._stop = True
        self._speaking = False
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()
            except ProcessLookupError:
                pass

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        if not self.voice_model.is_file():
            raise TTSError(f"Piper voice model not found: {self.voice_model}")
        self._stop = False
        self._speaking = True
        try:
            self._proc = await asyncio.create_subprocess_exec(
                self.binary,
                "--model",
                str(self.voice_model),
                "--output_raw",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            assert self._proc.stdin and self._proc.stdout
            self._proc.stdin.write((text.strip() + "\n").encode("utf-8"))
            await self._proc.stdin.drain()
            self._proc.stdin.close()
            while not self._stop:
                chunk = await self._proc.stdout.read(4096)
                if not chunk:
                    break
                yield chunk
            if self._proc.returncode is None:
                try:
                    await asyncio.wait_for(self._proc.wait(), timeout=1.0)
                except TimeoutError:
                    self.stop()
        finally:
            self._speaking = False
            self._proc = None


def create_tts(config: AppConfig, *, force_mock: bool = False) -> TextToSpeech:
    settings = config.speech_settings
    provider = "mock" if force_mock else str(settings.get("tts_provider", "mock")).lower()
    sample_rate = int(settings.get("sample_rate", 16000))
    if provider == "piper":
        return PiperTextToSpeech(
            binary=str(settings.get("piper_binary") or "piper"),
            voice_model=settings.get("piper_voice_model"),
            sample_rate=sample_rate,
        )
    return MockTextToSpeech(sample_rate=sample_rate)


def _silent_wav_chunk(*, sample_rate: int, duration_ms: int) -> bytes:
    frames = int(sample_rate * (duration_ms / 1000.0))
    pcm = b"\x00\x00" * frames
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buf.getvalue()
