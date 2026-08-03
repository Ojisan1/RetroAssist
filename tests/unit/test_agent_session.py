"""Session export markdown tests."""

from __future__ import annotations

from pathlib import Path

from retroassist.agent.export import (
    assert_export_contains,
    export_session_markdown,
    session_to_markdown,
)
from retroassist.agent.intake import apply_intake
from retroassist.agent.session import DiagnosticSession


def test_export_includes_core_sections(tmp_path: Path) -> None:
    session = DiagnosticSession()
    apply_intake(session, "No power", "PSU on bench")
    session.observations.append(
        {
            "summary": "PSU board visible",
            "latency_ms": 12.5,
            "latency_target_seconds": 6.0,
            "latency_within_target": True,
        }
    )
    session.retrievals.append(
        {
            "query": "fuse",
            "hits": [{"source": "notes.md", "page": 1, "text": "Check fuse", "score": 0.9}],
        }
    )
    session.suggestions.append(
        {
            "timestamp": session.created_at,
            "action": "Check fuse continuity",
            "expected_result": "Near 0 ohms",
            "rationale": "No power + fuse region",
            "confidence": 0.8,
            "safety_notes": ["Mains caution"],
            "citations": [{"source": "notes.md", "page": 1, "excerpt": "Check fuse"}],
        }
    )
    session.measurements.append({"timestamp": session.created_at, "text": "Fuse open"})
    session.latency_notes.append(
        {"timestamp": session.created_at, "label": "look_now", "latency_ms": 12.5}
    )

    md = session_to_markdown(session)
    assert_export_contains(
        md,
        [
            "# RetroAssist session",
            "## Intake",
            "No power",
            "## Observations",
            "## Retrieval",
            "## Suggestions",
            "Check fuse continuity",
            "## Measurements",
            "## Latency notes",
            "look_now",
        ],
    )
    path = export_session_markdown(session, tmp_path / "session.md")
    assert path.is_file()
    assert "No power" in path.read_text(encoding="utf-8")
