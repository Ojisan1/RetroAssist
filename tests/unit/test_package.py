"""Smoke tests for the package scaffold."""

from retroassist import __version__
from retroassist.interfaces import (
    AgentLoop,
    CaptureSource,
    KnowledgeStore,
    SpeechToText,
    TextToSpeech,
    VisionAnalyzer,
)


def test_version_is_set() -> None:
    assert __version__ == "0.1.0a1"


def test_interfaces_are_abstract() -> None:
    for cls in (
        CaptureSource,
        VisionAnalyzer,
        KnowledgeStore,
        AgentLoop,
        SpeechToText,
        TextToSpeech,
    ):
        assert getattr(cls, "__abstractmethods__", None)
