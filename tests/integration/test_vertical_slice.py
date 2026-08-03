"""Phase 5.5 vertical-slice gate checks (text path + basic suite)."""

from __future__ import annotations

from pathlib import Path

import pytest

from retroassist.agent.session import DiagnosticSession, IntakeRecord
from retroassist.cli_session import cmd_run_from_case
from retroassist.config import load_config
from retroassist.visual_suite import BASIC_CASES, run_suite


@pytest.mark.asyncio
async def test_basic_suite_green(tmp_path: Path) -> None:
    report = await run_suite(BASIC_CASES, work_dir=tmp_path)
    assert report.ok, "\n".join(report.summary_lines())
    for result in report.results:
        assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_cli_run_case_covers_gate_export(tmp_path: Path) -> None:
    cfg = load_config(platform_dir=tmp_path / "cfg")
    for stem in BASIC_CASES:
        out = tmp_path / f"{stem}.md"
        text = await cmd_run_from_case(
            config=cfg,
            work_dir=tmp_path / f"work-{stem}",
            case_stem=stem,
            export_path=out,
            mock=True,
        )
        assert out.is_file()
        md = out.read_text(encoding="utf-8")
        assert "## Intake" in md
        assert "## Observations" in md
        assert "## Suggestions" in md
        assert "## Latency notes" in md
        assert "latency" in text.lower() or "look now" in text.lower()


def test_session_roundtrip_dict() -> None:
    session = DiagnosticSession(session_id="abc")
    session.intake = IntakeRecord(symptom="No power", visual_notes="bench")
    session.observations.append({"summary": "PSU", "latency_ms": 1.5})
    session.latency_notes.append({"label": "look_now", "latency_ms": 1.5, "timestamp": 1.0})
    session.record("intake", {"symptom": "No power"})
    restored = DiagnosticSession.from_dict(session.to_dict())
    assert restored.session_id == "abc"
    assert restored.intake is not None
    assert restored.intake.symptom == "No power"
    assert restored.observations[0]["summary"] == "PSU"
    assert restored.events[0].kind == "intake"
