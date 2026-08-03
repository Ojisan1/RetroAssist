#!/usr/bin/env python3
"""Headless visual + agent regression runner (Phase 5.5 gate).

Usage (from repo root, editable install)::

    python tools/run_visual_suite.py
    python tools/run_visual_suite.py --all
    python tools/run_visual_suite.py --cases ps01,meter01
    retroassist test-visual --basic
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

# Editable / src layout
_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from retroassist.visual_suite import resolve_case_list, run_suite  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run RetroAssist mocked visual+agent suite")
    parser.add_argument("--basic", action="store_true", help="Gate cases only (default)")
    parser.add_argument("--all", action="store_true", dest="all_cases", help="Full Phase 5 suite")
    parser.add_argument("--cases", default=None, help="Comma-separated stems")
    args = parser.parse_args(argv)
    cases = resolve_case_list(basic=True, all_cases=args.all_cases, cases=args.cases)

    async def _run() -> int:
        import shutil

        tmp = tempfile.mkdtemp(prefix="retroassist-suite-")
        try:
            report = await run_suite(cases, work_dir=Path(tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print("\n".join(report.summary_lines()))
        return 0 if report.ok else 1

    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
