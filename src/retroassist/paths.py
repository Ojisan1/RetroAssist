"""Locate repository fixtures when running from an editable checkout."""

from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path | None:
    """Walk parents for ``pyproject.toml`` + ``tests/fixtures`` (editable installs)."""
    here = start or Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").is_file() and (parent / "tests" / "fixtures").is_dir():
            return parent
    return None


def fixtures_root() -> Path:
    root = find_repo_root()
    if root is None:
        raise FileNotFoundError(
            "Could not locate tests/fixtures (run from an editable RetroAssist checkout)."
        )
    return root / "tests" / "fixtures"


def samples_knowledge_root() -> Path:
    root = find_repo_root()
    if root is None:
        raise FileNotFoundError(
            "Could not locate samples/knowledge (run from an editable RetroAssist checkout)."
        )
    return root / "samples" / "knowledge"
