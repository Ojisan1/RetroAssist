"""Export diagnostic sessions to markdown."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from retroassist.agent.session import DiagnosticSession


def _fmt_ts(ts: float | None) -> str:
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def session_to_markdown(session: DiagnosticSession) -> str:
    """Render a first-class session log for expert review."""
    lines: list[str] = [
        f"# RetroAssist session `{session.session_id}`",
        "",
        f"- Created: {_fmt_ts(session.created_at)}",
        f"- Task tags: {', '.join(session.task_tags) or '(none)'}",
        "",
        "## Intake",
        "",
    ]
    if session.intake:
        lines.append(f"- Timestamp: {_fmt_ts(session.intake.timestamp)}")
        lines.append(f"- Symptom: {session.intake.symptom}")
        lines.append(f"- Visual notes: {session.intake.visual_notes or '(none)'}")
    else:
        lines.append("_No intake recorded._")

    lines.extend(["", "## Observations", ""])
    if not session.observations:
        lines.append("_No vision observations._")
    for idx, obs in enumerate(session.observations, start=1):
        lines.append(f"### Observation {idx}")
        lines.append(f"- Summary: {obs.get('summary', '')}")
        if obs.get("meter_reading") is not None:
            lines.append(f"- Meter reading: {obs.get('meter_reading')}")
        if obs.get("latency_ms") is not None:
            lines.append(
                f"- Vision latency: {obs.get('latency_ms'):.1f} ms "
                f"(target {obs.get('latency_target_seconds')} s, "
                f"within={obs.get('latency_within_target')})"
            )
        lines.append("")

    lines.extend(["## Retrieval", ""])
    if not session.retrievals:
        lines.append("_No retrieval calls (or empty knowledge base)._")
    for idx, block in enumerate(session.retrievals, start=1):
        lines.append(f"### Retrieval {idx}")
        lines.append(f"- Query: {block.get('query', '')}")
        hits = block.get("hits") or []
        if not hits:
            lines.append("- Hits: _(none — do not invent manual citations)_")
        for hit in hits:
            page = hit.get("page")
            page_bit = f", page {page}" if page is not None else ""
            lines.append(
                f"- cite: `{hit.get('source')}`{page_bit} score={hit.get('score')}"
            )
            excerpt = (hit.get("text") or "")[:240]
            if excerpt:
                lines.append(f"  - excerpt: {excerpt}")
        lines.append("")

    lines.extend(["## Suggestions", ""])
    if not session.suggestions:
        lines.append("_No suggestions yet._")
    for idx, sug in enumerate(session.suggestions, start=1):
        lines.append(f"### Suggestion {idx}")
        lines.append(f"- Timestamp: {_fmt_ts(sug.get('timestamp'))}")
        lines.append(f"- Action: {sug.get('action', '')}")
        lines.append(f"- Expected result: {sug.get('expected_result', '')}")
        lines.append(f"- Rationale: {sug.get('rationale', '')}")
        lines.append(f"- Confidence: {sug.get('confidence', '')}")
        notes = sug.get("safety_notes") or []
        if notes:
            lines.append("- Safety notes:")
            for note in notes:
                lines.append(f"  - {note}")
        citations = sug.get("citations") or []
        if citations:
            lines.append("- Citations:")
            for cite in citations:
                lines.append(
                    f"  - {cite.get('source')} "
                    f"(page={cite.get('page')}): {cite.get('excerpt')}"
                )
        elif sug.get("kb_empty"):
            lines.append("- Citations: _(none; empty KB — no fabricated manual pages)_")
        lines.append("")

    lines.extend(["## Measurements / technician reports", ""])
    if not session.measurements:
        lines.append("_None recorded._")
    for item in session.measurements:
        lines.append(f"- {_fmt_ts(item.get('timestamp'))}: {item.get('text', '')}")

    lines.extend(["", "## Latency notes", ""])
    if not session.latency_notes:
        lines.append("_No latency notes._")
    for note in session.latency_notes:
        lines.append(
            f"- {_fmt_ts(note.get('timestamp'))}: {note.get('label')} "
            f"= {note.get('latency_ms')} ms"
        )

    lines.extend(["", "## Event log", ""])
    for event in session.events:
        lines.append(f"- {_fmt_ts(event.timestamp)} `{event.kind}`")

    lines.append("")
    return "\n".join(lines)


def export_session_markdown(session: DiagnosticSession, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(session_to_markdown(session), encoding="utf-8")
    return out


def assert_export_contains(markdown: str, required: list[str]) -> None:
    """Test helper: ensure required substrings exist in an export."""
    missing = [item for item in required if item not in markdown]
    if missing:
        raise AssertionError(f"Export missing required sections/strings: {missing}")
