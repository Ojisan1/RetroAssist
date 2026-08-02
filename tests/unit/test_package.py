"""Smoke tests for the Phase 0 package scaffold."""

from retroassist import __version__


def test_version_is_set() -> None:
    assert __version__ == "0.0.1"
