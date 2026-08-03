"""Build rolling context bundles for the diagnostic agent."""

from __future__ import annotations

from typing import Any

from retroassist.agent.session import DiagnosticSession


def build_context_bundle(
    session: DiagnosticSession,
    *,
    query: str | None = None,
    retrieval_hits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble intake + latest vision + memory + retrieval for prompting."""
    observation = session.observations[-1] if session.observations else None
    hits = retrieval_hits if retrieval_hits is not None else (
        session.retrievals[-1]["hits"] if session.retrievals else []
    )
    intake = session.intake
    return {
        "session_id": session.session_id,
        "symptom": intake.symptom if intake else "",
        "visual_notes": intake.visual_notes if intake else "",
        "query": query or "",
        "observation": observation,
        "measurements": list(session.measurements[-8:]),
        "steps_tried": list(session.steps_tried[-12:]),
        "retrieval_hits": list(hits),
        "task_tags": list(session.task_tags),
    }


def remember_step(session: DiagnosticSession, action: str) -> None:
    action = (action or "").strip()
    if action and action not in session.steps_tried:
        session.steps_tried.append(action)


def format_hits_for_prompt(hits: list[dict[str, Any]], *, limit: int = 5) -> str:
    if not hits:
        return "(no retrieved documentation; do not invent manual page citations)"
    lines: list[str] = []
    for hit in hits[:limit]:
        source = hit.get("source") or hit.get("metadata", {}).get("source") or "unknown"
        page = hit.get("page") or hit.get("metadata", {}).get("page")
        excerpt = (hit.get("text") or "")[:400]
        page_bit = f", page {page}" if page is not None else ""
        lines.append(f"- source={source}{page_bit}: {excerpt}")
    return "\n".join(lines)
