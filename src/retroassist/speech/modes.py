"""PTT and open-mic capture modes with simple energy VAD and barge-in."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from retroassist.config import AppConfig, SpeechMode


class MicSource(Protocol):
    """Async PCM16 mono chunk source."""

    async def chunks(self, *, sample_rate: int, chunk_ms: int = 30) -> AsyncIterator[bytes]:
        ...


@dataclass
class MockMicSource:
    """Deterministic mic for CI: yields prepared PCM chunks then silence."""

    pcm_chunks: list[bytes]
    trailing_silence_chunks: int = 5

    async def chunks(
        self, *, sample_rate: int = 16000, chunk_ms: int = 30
    ) -> AsyncIterator[bytes]:
        silence = b"\x00\x00" * max(1, int(sample_rate * (chunk_ms / 1000.0)))
        for chunk in self.pcm_chunks:
            yield chunk
            await asyncio.sleep(0)
        for _ in range(self.trailing_silence_chunks):
            yield silence
            await asyncio.sleep(0)


def pcm_rms_energy(pcm16: bytes) -> float:
    """RMS energy of little-endian int16 PCM mono in 0..1-ish range."""
    if not pcm16:
        return 0.0
    # Ensure even length
    if len(pcm16) % 2:
        pcm16 = pcm16[:-1]
    samples = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(samples))))
    return rms / 32768.0


class SpeechModeController:
    """PTT / open-mic utterance capture + barge-in signaling."""

    def __init__(
        self,
        *,
        mode: SpeechMode = "ptt",
        sample_rate: int = 16000,
        vad_energy_threshold: float = 0.02,
        vad_silence_ms: int = 700,
        vad_min_speech_ms: int = 250,
        ptt_max_seconds: float = 15.0,
        open_mic_max_seconds: float = 20.0,
        on_barge_in: Callable[[], None] | None = None,
    ) -> None:
        self.mode = mode
        self.sample_rate = sample_rate
        self.vad_energy_threshold = vad_energy_threshold
        self.vad_silence_ms = vad_silence_ms
        self.vad_min_speech_ms = vad_min_speech_ms
        self.ptt_max_seconds = ptt_max_seconds
        self.open_mic_max_seconds = open_mic_max_seconds
        self.on_barge_in = on_barge_in
        self._barge_in = False

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        on_barge_in: Callable[[], None] | None = None,
    ) -> SpeechModeController:
        s = config.speech_settings
        return cls(
            mode=config.speech_mode,
            sample_rate=int(s.get("sample_rate", 16000)),
            vad_energy_threshold=float(s.get("vad_energy_threshold", 0.02)),
            vad_silence_ms=int(s.get("vad_silence_ms", 700)),
            vad_min_speech_ms=int(s.get("vad_min_speech_ms", 250)),
            ptt_max_seconds=float(s.get("ptt_max_seconds", 15.0)),
            open_mic_max_seconds=float(s.get("open_mic_max_seconds", 20.0)),
            on_barge_in=on_barge_in,
        )

    def set_mode(self, mode: SpeechMode) -> None:
        if mode not in ("ptt", "open_mic"):
            raise ValueError(f"speech mode must be ptt|open_mic, got {mode!r}")
        self.mode = mode

    def request_barge_in(self) -> None:
        self._barge_in = True
        if self.on_barge_in:
            self.on_barge_in()

    def clear_barge_in(self) -> None:
        self._barge_in = False

    @property
    def barge_in_requested(self) -> bool:
        return self._barge_in

    def is_speech(self, pcm_chunk: bytes) -> bool:
        return pcm_rms_energy(pcm_chunk) >= self.vad_energy_threshold

    async def capture_utterance(
        self,
        mic: MicSource,
        *,
        ptt_pressed: bool = True,
        chunk_ms: int = 30,
    ) -> bytes:
        """Capture one utterance according to current mode.

        PTT: collect while ``ptt_pressed`` (caller holds true for the press window)
        by gathering until max duration or mic ends. For mock mics, ``ptt_pressed``
        True means take the whole provided stream up to ``ptt_max_seconds``.

        Open-mic: wait for speech → collect until silence of ``vad_silence_ms``.
        Speaking over TTS triggers barge-in when speech energy is detected.
        """
        if self.mode == "ptt":
            return await self._capture_ptt(mic, ptt_pressed=ptt_pressed, chunk_ms=chunk_ms)
        return await self._capture_open_mic(mic, chunk_ms=chunk_ms)

    async def _capture_ptt(
        self,
        mic: MicSource,
        *,
        ptt_pressed: bool,
        chunk_ms: int,
    ) -> bytes:
        if not ptt_pressed:
            return b""
        max_chunks = max(1, int((self.ptt_max_seconds * 1000) / chunk_ms))
        buf = bytearray()
        count = 0
        async for chunk in mic.chunks(sample_rate=self.sample_rate, chunk_ms=chunk_ms):
            buf.extend(chunk)
            count += 1
            if count >= max_chunks:
                break
        return bytes(buf)

    async def _capture_open_mic(self, mic: MicSource, *, chunk_ms: int) -> bytes:
        max_chunks = max(1, int((self.open_mic_max_seconds * 1000) / chunk_ms))
        silence_needed = max(1, int(self.vad_silence_ms / chunk_ms))
        min_speech = max(1, int(self.vad_min_speech_ms / chunk_ms))

        buf = bytearray()
        started = False
        speech_chunks = 0
        silence_chunks = 0
        total = 0
        started_at = time.perf_counter()

        async for chunk in mic.chunks(sample_rate=self.sample_rate, chunk_ms=chunk_ms):
            total += 1
            speech = self.is_speech(chunk)
            if speech:
                if not started:
                    started = True
                    # Barge-in if TTS may be speaking
                    self.request_barge_in()
                speech_chunks += 1
                silence_chunks = 0
                buf.extend(chunk)
            elif started:
                silence_chunks += 1
                buf.extend(chunk)
                if speech_chunks >= min_speech and silence_chunks >= silence_needed:
                    break
            if total >= max_chunks:
                break
            # Soft bound by wall clock also
            if (time.perf_counter() - started_at) >= self.open_mic_max_seconds:
                break

        return bytes(buf)
