"""CLI smoke tests."""

from __future__ import annotations

import pytest

from retroassist.__main__ import build_parser, main


def test_parser_has_phase1_commands() -> None:
    parser = build_parser()
    # argparse stores subparsers; ensure required commands exist by parsing help path
    for cmd in ("doctor", "serve", "test-visual"):
        args = parser.parse_args([cmd])
        assert args.command == cmd


def test_test_visual_not_implemented(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["test-visual"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "later phase" in err.lower() or "reserved" in err.lower()
