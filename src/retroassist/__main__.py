"""CLI entry point for RetroAssist."""

from __future__ import annotations


def main() -> None:
    """Minimal Phase 0 entry point; real commands arrive in later phases."""
    from retroassist import __version__

    print(f"RetroAssist {__version__} (pre-alpha scaffold)")


if __name__ == "__main__":
    main()
