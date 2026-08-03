"""Diagnostic session state and append-only event log."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


def _now() -> float:
    return time.time()


@dataclass
class IntakeRecord:
    symptom: str
    visual_notes: str = ""
    timestamp: float = field(default_factory=_now)


@dataclass
class SessionEvent:
    kind: str
    timestamp: float
    payload: dict[str, Any]


@dataclass
class DiagnosticSession:
    """In-memory diagnostic session used by the agent loop and exporters."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=_now)
    intake: IntakeRecord | None = None
    observations: list[dict[str, Any]] = field(default_factory=list)
    retrievals: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    measurements: list[dict[str, Any]] = field(default_factory=list)
    steps_tried: list[str] = field(default_factory=list)
    latency_notes: list[dict[str, Any]] = field(default_factory=list)
    events: list[SessionEvent] = field(default_factory=list)
    task_tags: list[str] = field(default_factory=list)

    def record(self, kind: str, payload: dict[str, Any]) -> SessionEvent:
        event = SessionEvent(kind=kind, timestamp=_now(), payload=payload)
        self.events.append(event)
        return event

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "intake": asdict(self.intake) if self.intake else None,
            "observations": list(self.observations),
            "retrievals": list(self.retrievals),
            "suggestions": list(self.suggestions),
            "measurements": list(self.measurements),
            "steps_tried": list(self.steps_tried),
            "latency_notes": list(self.latency_notes),
            "task_tags": list(self.task_tags),
            "events": [asdict(e) for e in self.events],
        }
