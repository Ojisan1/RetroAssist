"""Voice intent parsing for workbench dialogue."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class Intent(StrEnum):
    LOOK_NOW = "look_now"
    NEXT_STEP = "next_step"
    REPORT_MEASUREMENT = "report_measurement"
    CLARIFY = "clarify"
    STOP_SPEAKING = "stop_speaking"
    EXPORT_SESSION = "export_session"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentResult:
    intent: Intent
    text: str
    payload: str = ""


_STOP = re.compile(
    r"\b(stop speaking|stop talking|be quiet|shut up|silence|cancel speech)\b",
    re.I,
)
_LOOK = re.compile(
    r"\b(look now|look at (the )?(board|bench)|what do you see|describe what you see)\b",
    re.I,
)
_EXPORT = re.compile(
    r"\b(export( the)? session|save( the)? session|export (the )?log)\b",
    re.I,
)
_NEXT = re.compile(
    r"\b("
    r"what (should|do) i (check|do|try) next"
    r"|next step"
    r"|what('?s| is) next"
    r"|suggest( a)? (next|check)"
    r"|what first"
    r"|check first"
    r")\b",
    re.I,
)
_MEASURE = re.compile(
    r"\b("
    r"(i('?m| am) )?(measuring|measured|reading|getting|see|seeing)"
    r"|reads?|read(?:ing)?"
    r"|volts?|millivolts?|amps?|ohms?"
    r"|continuity|open fuse|shorted"
    r")\b",
    re.I,
)
_CLARIFY = re.compile(
    r"\b("
    r"(can you )?(clarify|explain|repeat)"
    r"|what (did you|do you) mean"
    r"|say that again"
    r"|is that (normal|ok|okay|in range|within range)"
    r")\b",
    re.I,
)


def parse_intent(transcript: str) -> IntentResult:
    """Map a technician utterance to a dialogue intent."""
    text = (transcript or "").strip()
    if not text:
        return IntentResult(Intent.UNKNOWN, text)

    if _STOP.search(text):
        return IntentResult(Intent.STOP_SPEAKING, text)
    if _EXPORT.search(text):
        return IntentResult(Intent.EXPORT_SESSION, text)
    if _LOOK.search(text):
        return IntentResult(Intent.LOOK_NOW, text)
    if _NEXT.search(text):
        return IntentResult(Intent.NEXT_STEP, text, payload=text)
    if _MEASURE.search(text):
        return IntentResult(Intent.REPORT_MEASUREMENT, text, payload=text)
    if _CLARIFY.search(text):
        return IntentResult(Intent.CLARIFY, text, payload=text)

    # Default: treat free-form diagnostic talk as next-step / ask
    return IntentResult(Intent.NEXT_STEP, text, payload=text)
