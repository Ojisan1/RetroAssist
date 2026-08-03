"""CLI smoke / Phase 5.5 command tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from retroassist.__main__ import build_parser, main


def test_parser_has_phase55_commands() -> None:
    parser = build_parser()
    for cmd in ("doctor", "serve", "test-visual", "listen"):
        args = parser.parse_args([cmd] if cmd != "listen" else [cmd, "--transcript", "hi"])
        assert args.command == cmd
    args = parser.parse_args(["session", "export", "--out", "x.md"])
    assert args.command == "session"
    assert args.session_command == "export"


def test_session_run_parser() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["session", "run", "--case", "ps01", "--out", "out.md", "--mock"]
    )
    assert args.command == "session"
    assert args.session_command == "run"
    assert args.case == "ps01"
    assert args.mock is True


def test_test_visual_basic_green() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["test-visual", "--basic"])
    assert exc.value.code == 0


def test_session_run_ps01_exports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "ps01.md"
    state = tmp_path / "state.json"
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "session",
                "run",
                "--state",
                str(state),
                "--case",
                "ps01",
                "--out",
                str(out),
                "--mock",
            ]
        )
    assert exc.value.code == 0
    text = out.read_text(encoding="utf-8")
    assert "## Intake" in text
    assert "No power" in text
    assert "## Suggestions" in text
    assert "## Latency notes" in text
    captured = capsys.readouterr().out
    assert "latency" in captured.lower() or "look now" in captured.lower()


def test_session_stepwise_fixture_path(tmp_path: Path) -> None:
    from retroassist.paths import fixtures_root

    state = tmp_path / "cli_state.json"
    image = fixtures_root() / "images" / "power_supply" / "sample.png"
    assert image.is_file()

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "session",
                "intake",
                "--state",
                str(state),
                "--mock",
                "--vision-case",
                "power_supply",
                "--agent-case",
                "ps01",
                "--kb-sample",
                "synthetic_psu_notes.md",
                "--symptom",
                "No power at all.",
                "--notes",
                "PSU on bench",
            ]
        )
    assert exc.value.code == 0

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "session",
                "look-now",
                "--state",
                str(state),
                "--mock",
                "--vision-case",
                "power_supply",
                "--agent-case",
                "ps01",
                "--kb-sample",
                "synthetic_psu_notes.md",
                "--image",
                str(image),
            ]
        )
    assert exc.value.code == 0

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "session",
                "next",
                "--state",
                str(state),
                "--mock",
                "--agent-case",
                "ps01",
                "--kb-sample",
                "synthetic_psu_notes.md",
                "--query",
                "What should I check first?",
            ]
        )
    assert exc.value.code == 0

    out = tmp_path / "export.md"
    with pytest.raises(SystemExit) as exc:
        main(["session", "export", "--state", str(state), "--out", str(out)])
    assert exc.value.code == 0
    md = out.read_text(encoding="utf-8")
    assert "No power at all." in md
    assert "## Observations" in md
    assert "## Event log" in md


def test_tools_run_visual_suite_script() -> None:
    repo = Path(__file__).resolve().parents[2]
    tool = repo / "tools" / "run_visual_suite.py"
    assert tool.is_file()
    proc = subprocess.run(
        [sys.executable, str(tool), "--cases", "empty01"],
        cwd=str(repo),
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout
