"""Speech-to-text: mock (CI), faster-whisper, optional cloud opt-in."""

from __future__ import annotations

import io
import json
import wave
from pathlib import Path
from typing import Any

from retroassist.config import AppConfig
from retroassist.interfaces import SpeechToText


class SpeechError(Exception):
    """STT failure."""


class MockSpeechToText(SpeechToText):
    """CI-safe STT: returns a fixed transcript or looks up fixture sidecars."""

    def __init__(
        self,
        transcript: str = "What should I check next?",
        *,
        fixture_map: dict[str, str] | None = None,
    ) -> None:
        self.transcript = transcript
        self.fixture_map = fixture_map or {}
        self.calls: list[dict[str, Any]] = []

    def set_transcript(self, text: str) -> None:
        self.transcript = text

    async def transcribe(self, audio: bytes, *, sample_rate: int = 16000) -> str:
        self.calls.append({"sample_rate": sample_rate, "bytes": len(audio)})
        # Optional: WAV comment / paired path encoded as JSON prefix is unused;
        # fingerprint by length+checksum for fixture map keys when provided.
        key = f"len:{len(audio)}"
        if key in self.fixture_map:
            return self.fixture_map[key]
        # Sidecar style: if audio starts with UTF-8 marker used in tests
        if audio.startswith(b"MOCKTRANSCRIPT:"):
            return audio.removeprefix(b"MOCKTRANSCRIPT:").decode("utf-8", errors="replace")
        return self.transcript


class WhisperSpeechToText(SpeechToText):
    """Local faster-whisper STT (optional ``[speech]`` extra)."""

    def __init__(
        self,
        *,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SpeechError(
                "faster-whisper is not installed. "
                "Install with: pip install 'retroassist[speech]'"
            ) from exc
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.model_size = model_size

    async def transcribe(self, audio: bytes, *, sample_rate: int = 16000) -> str:
        import asyncio

        def _run() -> str:
            pcm = _audio_bytes_to_wav_path(audio, sample_rate=sample_rate)
            try:
                segments, _info = self._model.transcribe(str(pcm), language="en")
                return " ".join(seg.text.strip() for seg in segments).strip()
            finally:
                Path(pcm).unlink(missing_ok=True)

        return await asyncio.to_thread(_run)


class CloudSpeechToText(SpeechToText):
    """Optional cloud STT — only constructed when ``cloud_opt_in`` is true."""

    def __init__(self, *, url: str, api_key: str | None = None) -> None:
        if not url:
            raise SpeechError("cloud_stt_url is required when cloud_opt_in is true")
        self.url = url
        self.api_key = api_key or ""

    async def transcribe(self, audio: bytes, *, sample_rate: int = 16000) -> str:
        import httpx

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.url,
                content=audio,
                headers={**headers, "Content-Type": "application/octet-stream"},
                params={"sample_rate": sample_rate},
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "text" in data:
                return str(data["text"])
            return str(data)


def create_stt(config: AppConfig, *, force_mock: bool = False) -> SpeechToText:
    """Factory: mock by default; whisper/cloud only when configured + available."""
    settings = config.speech_settings
    provider = "mock" if force_mock else str(settings.get("stt_provider", "mock")).lower()

    if settings.get("cloud_opt_in") and provider == "cloud":
        return CloudSpeechToText(
            url=str(settings.get("cloud_stt_url") or ""),
            api_key=config.llm_api_key,
        )

    if provider == "whisper":
        return WhisperSpeechToText(
            model_size=str(settings.get("whisper_model", "base")),
            device=str(settings.get("whisper_device", "cpu")),
        )

    transcript = str(settings.get("mock_transcript") or "What should I check next?")
    return MockSpeechToText(transcript=transcript)


def load_fixture_transcript(path: Path) -> str:
    """Load transcript from a ``.json`` sidecar or ``.txt`` next to a WAV."""
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "transcript" in data:
            return str(data["transcript"])
        raise SpeechError(f"Fixture JSON missing transcript: {path}")
    return path.read_text(encoding="utf-8").strip()


def _audio_bytes_to_wav_path(audio: bytes, *, sample_rate: int) -> Path:
    """Write PCM16 mono or pass-through WAV to a temp file for whisper."""
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    if audio[:4] == b"RIFF":
        tmp_path.write_bytes(audio)
        return tmp_path
    # Assume raw PCM16 little-endian mono
    with wave.open(str(tmp_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(audio)
    return tmp_path


def pcm16_mono_wav_bytes(pcm: bytes, *, sample_rate: int = 16000) -> bytes:
    """Wrap raw PCM16 mono as a WAV blob."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buf.getvalue()
