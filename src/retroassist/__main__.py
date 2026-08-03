"""CLI entry point for RetroAssist."""

from __future__ import annotations

import argparse
import asyncio
import sys

from retroassist import __version__
from retroassist.config import load_config
from retroassist.doctor import format_report, run_doctor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="retroassist",
        description="Local-first classic electronics repair assistant",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to a YAML config file (merged on top of defaults/platform/project)",
    )

    sub = parser.add_subparsers(dest="command")

    doctor_p = sub.add_parser("doctor", help="Check local environment (Python, config, Ollama)")
    doctor_p.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM/Ollama reachability checks",
    )

    serve_p = sub.add_parser("serve", help="Start the local FastAPI server")
    serve_p.add_argument("--host", default=None, help="Override server.host")
    serve_p.add_argument("--port", type=int, default=None, help="Override server.port")

    # Placeholder reserved for Phase 3+
    sub.add_parser(
        "test-visual",
        help="Run visual keyframe suite (not implemented until later phases)",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        raise SystemExit(0)

    config_path = None
    if args.config:
        from pathlib import Path

        config_path = Path(args.config)

    if args.command == "doctor":
        cfg = load_config(config_path=config_path)
        report = asyncio.run(run_doctor(cfg, check_llm=not args.skip_llm))
        print(format_report(report))
        raise SystemExit(0 if report.ok else 1)

    if args.command == "serve":
        cfg = load_config(config_path=config_path)
        host = args.host or cfg.server_host
        port = args.port if args.port is not None else cfg.server_port
        _serve(cfg, host=host, port=port)
        return

    if args.command == "test-visual":
        print(
            "retroassist test-visual is reserved for a later phase "
            "(visual keyframe + agent suite).",
            file=sys.stderr,
        )
        raise SystemExit(2)

    parser.error(f"Unknown command: {args.command}")


def _serve(cfg: object, *, host: str, port: int) -> None:
    import uvicorn

    from retroassist.app import create_app
    from retroassist.config import AppConfig

    assert isinstance(cfg, AppConfig)
    app = create_app(cfg)
    print(f"RetroAssist {__version__} serving on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
