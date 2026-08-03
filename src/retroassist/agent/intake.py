"""Session intake helpers (text-first)."""

from __future__ import annotations

from retroassist.agent.session import DiagnosticSession, IntakeRecord


class IntakeError(ValueError):
    """Invalid intake input."""


def apply_intake(
    session: DiagnosticSession,
    symptom: str,
    visual_notes: str = "",
) -> IntakeRecord:
    """Record technician symptom + visual notes on the session."""
    cleaned = (symptom or "").strip()
    if not cleaned:
        raise IntakeError("Intake requires a non-empty symptom description.")
    notes = (visual_notes or "").strip()
    record = IntakeRecord(symptom=cleaned, visual_notes=notes)
    session.intake = record
    session.record(
        "intake",
        {"symptom": record.symptom, "visual_notes": record.visual_notes},
    )
    # Lightweight task tagging for longevity/mod wording
    lowered = f"{cleaned} {notes}".lower()
    tags: list[str] = []
    if any(k in lowered for k in ("capacitor", "recap", "cap replacement")):
        tags.append("longevity")
    if any(k in lowered for k in ("mod", "hdmi", "rgb", "scart", "battery upgrade")):
        tags.append("modification")
    for tag in tags:
        if tag not in session.task_tags:
            session.task_tags.append(tag)
    return record
