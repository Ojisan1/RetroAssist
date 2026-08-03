"""Protocol / ABC interfaces for RetroAssist modules.

Concrete implementations arrive in later phases; these define the contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from typing import Any


class CaptureSource(ABC):
    """Provides workbench camera frames (USB, capture card, OBS Virtual Camera)."""

    @abstractmethod
    def open(self) -> None:
        """Open the capture device."""

    @abstractmethod
    def close(self) -> None:
        """Release the capture device."""

    @abstractmethod
    def read(self) -> Any | None:
        """Return the latest frame, or None if unavailable."""

    @abstractmethod
    def is_open(self) -> bool:
        """Whether the source is currently open."""


class VisionAnalyzer(ABC):
    """Turns one or more frames into structured observations."""

    @abstractmethod
    async def analyze(
        self,
        frames: Sequence[Any],
        *,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        """Analyze frames and return a structured observation dict."""


class KnowledgeStore(ABC):
    """Ingest and retrieve schematics / service documentation."""

    @abstractmethod
    async def ingest(self, path: str, *, metadata: dict[str, Any] | None = None) -> int:
        """Import a document; return number of chunks indexed."""

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
        vision_summary: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return ranked retrieval hits (empty list if KB is empty)."""


class AgentLoop(ABC):
    """Fuses vision + RAG + session context into next-step suggestions."""

    @abstractmethod
    async def intake(self, symptom: str, visual_notes: str = "") -> None:
        """Record initial session intake."""

    @abstractmethod
    async def suggest_next(self) -> dict[str, Any]:
        """Propose the next diagnostic step(s)."""

    @abstractmethod
    async def report_measurement(self, text: str) -> dict[str, Any]:
        """Incorporate a technician-reported measurement or observation."""


class SpeechToText(ABC):
    """Local speech-to-text."""

    @abstractmethod
    async def transcribe(self, audio: bytes, *, sample_rate: int = 16000) -> str:
        """Transcribe PCM/WAV audio bytes to text."""


class TextToSpeech(ABC):
    """Local text-to-speech."""

    @abstractmethod
    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Yield audio chunks for the given text."""

    def stop(self) -> None:  # noqa: B027 — optional barge-in hook for concrete TTS
        """Interrupt current synthesis (barge-in). Default no-op."""

    @property
    def speaking(self) -> bool:
        """Whether synthesis is in progress."""
        return False
