"""CLI entry point for RetroAssist."""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

from retroassist import __version__
from retroassist.config import load_config
from retroassist.doctor import format_report, run_doctor


def _session_common_parent() -> argparse.ArgumentParser:
    """Flags shared by all ``session`` subcommands (usable after the verb)."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--state",
        type=str,
        default=None,
        help="Path to CLI session state JSON (default: <sessions>/cli_state.json)",
    )
    parent.add_argument(
        "--mock",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use mocked VLM + agent LLM (default: true; --no-mock = live Ollama)",
    )
    parent.add_argument(
        "--vision-case",
        default="power_supply",
        help="Mock VLM case id (when --mock)",
    )
    parent.add_argument(
        "--agent-case",
        default="ps01",
        help="Mock agent suggestion case id (when --mock)",
    )
    parent.add_argument(
        "--empty-kb",
        action="store_true",
        help="Force empty knowledge base (no sample ingest)",
    )
    parent.add_argument(
        "--kb-sample",
        action="append",
        default=[],
        help="Sample knowledge file under samples/knowledge/ (repeatable)",
    )
    return parent


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

    session_common = _session_common_parent()
    session_p = sub.add_parser(
        "session",
        help="Text vertical slice: intake → look-now → next → export",
    )
    session_sub = session_p.add_subparsers(dest="session_command", required=True)

    intake_p = session_sub.add_parser(
        "intake", parents=[session_common], help="Record symptom + visual notes"
    )
    intake_p.add_argument("--symptom", required=True)
    intake_p.add_argument("--notes", default="", help="Technician visual notes")

    look_p = session_sub.add_parser(
        "look-now", parents=[session_common], help="Analyze a fixture or captured still"
    )
    look_p.add_argument("--image", required=True, help="Path to keyframe / still image")

    next_p = session_sub.add_parser(
        "next", parents=[session_common], help="Suggest next diagnostic step"
    )
    next_p.add_argument(
        "--query", default=None, help="Technician query (default: last / symptom)"
    )

    export_p = session_sub.add_parser(
        "export", parents=[session_common], help="Write session markdown"
    )
    export_p.add_argument("--out", required=True, help="Output .md path")

    run_p = session_sub.add_parser(
        "run",
        parents=[session_common],
        help="One-shot slice: intake → look-now → next → export",
    )
    run_p.add_argument(
        "--case",
        default=None,
        help="Query fixture stem (e.g. ps01); fills symptom/image/query/kb from fixtures",
    )
    run_p.add_argument("--symptom", default=None)
    run_p.add_argument("--notes", default="")
    run_p.add_argument("--image", default=None)
    run_p.add_argument("--query", default=None)
    run_p.add_argument("--out", required=True, help="Export markdown path")

    visual_p = sub.add_parser(
        "test-visual",
        help="Run mocked visual+agent keyframe suite (Phase 5.5 gate)",
    )
    visual_p.add_argument(
        "--basic",
        action="store_true",
        help="Gate set: PS-01, METER-01, EMPTY-01, NO-KB-01 (default)",
    )
    visual_p.add_argument(
        "--all",
        action="store_true",
        dest="all_cases",
        help="Full Phase 5 suite including PS-02 and LOGIC-01",
    )
    visual_p.add_argument(
        "--cases",
        default=None,
        help="Comma-separated fixture stems (e.g. ps01,meter01)",
    )

    listen_p = sub.add_parser(
        "listen",
        help="Voice turn: STT → intent → agent → TTS (mock audio/text for CI)",
    )
    listen_p.add_argument(
        "--mode",
        choices=("ptt", "open_mic"),
        default=None,
        help="Override speech.mode for this run",
    )
    listen_p.add_argument(
        "--mock",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Mock STT/TTS + mocked agent/vision (default: true)",
    )
    listen_p.add_argument(
        "--transcript",
        default=None,
        help="Skip mic/STT and use this text (typed voice fallback)",
    )
    listen_p.add_argument(
        "--audio",
        default=None,
        help="WAV/PCM audio file to transcribe (mock STT may use sidecar JSON)",
    )
    listen_p.add_argument(
        "--case",
        default=None,
        help="Query fixture stem to seed intake/vision/agent mock (e.g. ps01)",
    )
    listen_p.add_argument(
        "--agent-case",
        default="ps01",
        help="Mock agent response case when not using --case",
    )
    listen_p.add_argument(
        "--image",
        default=None,
        help="Optional fixture image for look_now intent",
    )
    listen_p.add_argument(
        "--state",
        default=None,
        help="Optional CLI session state path (persist agent session)",
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

    if args.command == "session":
        cfg = load_config(config_path=config_path)
        raise SystemExit(asyncio.run(_session_command(cfg, args)))

    if args.command == "test-visual":
        raise SystemExit(asyncio.run(_test_visual(args)))

    if args.command == "listen":
        cfg = load_config(config_path=config_path)
        raise SystemExit(asyncio.run(_listen_command(cfg, args)))

    parser.error(f"Unknown command: {args.command}")


async def _session_command(cfg: object, args: argparse.Namespace) -> int:
    from retroassist.cli_session import (
        cmd_export,
        cmd_intake,
        cmd_look_now,
        cmd_next,
        cmd_run,
        cmd_run_from_case,
        default_state_path,
        load_state,
        save_state,
    )
    from retroassist.config import AppConfig

    assert isinstance(cfg, AppConfig)
    state_path = Path(args.state) if args.state else default_state_path(cfg)
    work_dir = state_path.parent / f".work-{state_path.stem}"
    work_dir.mkdir(parents=True, exist_ok=True)

    if args.session_command == "run":
        export_path = Path(args.out)
        try:
            if args.case:
                text = await cmd_run_from_case(
                    config=cfg,
                    work_dir=work_dir,
                    case_stem=str(args.case).lower(),
                    export_path=export_path,
                    mock=bool(args.mock),
                )
            else:
                if not args.symptom or not args.image or not args.query:
                    print(
                        "session run requires --case OR (--symptom, --image, and --query)",
                        file=sys.stderr,
                    )
                    return 2
                text = await cmd_run(
                    config=cfg,
                    work_dir=work_dir,
                    symptom=args.symptom,
                    visual_notes=args.notes or "",
                    image=Path(args.image),
                    query=args.query,
                    export_path=export_path,
                    mock=bool(args.mock),
                    vision_case=args.vision_case,
                    agent_case=args.agent_case,
                    empty_kb=bool(args.empty_kb),
                    kb_samples=list(args.kb_sample or []),
                )
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(text)
        return 0

    state = load_state(state_path)
    state.mock = bool(args.mock)
    state.vision_case = args.vision_case
    state.agent_case = args.agent_case
    if args.empty_kb:
        state.empty_kb = True
    if args.kb_sample:
        state.kb_samples = list(args.kb_sample)

    try:
        if args.session_command == "intake":
            msg = await cmd_intake(
                state,
                config=cfg,
                work_dir=work_dir,
                symptom=args.symptom,
                visual_notes=args.notes or "",
            )
        elif args.session_command == "look-now":
            msg = await cmd_look_now(
                state,
                config=cfg,
                work_dir=work_dir,
                image=Path(args.image),
            )
        elif args.session_command == "next":
            msg = await cmd_next(
                state,
                config=cfg,
                work_dir=work_dir,
                query=args.query,
            )
        elif args.session_command == "export":
            msg = cmd_export(state, out=Path(args.out))
        else:
            print(f"Unknown session command: {args.session_command}", file=sys.stderr)
            return 2
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    save_state(state_path, state)
    print(msg)
    return 0


async def _test_visual(args: argparse.Namespace) -> int:
    from retroassist.visual_suite import resolve_case_list, run_suite

    cases = resolve_case_list(
        basic=True,
        all_cases=bool(args.all_cases),
        cases=args.cases,
    )
    tmp = tempfile.mkdtemp(prefix="retroassist-visual-")
    try:
        report = await run_suite(cases, work_dir=Path(tmp))
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
    print("\n".join(report.summary_lines()))
    return 0 if report.ok else 1


async def _listen_command(cfg: object, args: argparse.Namespace) -> int:
    """One voice turn (transcript, audio file, or mock mic) — text fallback always works."""
    from retroassist.cli_session import SliceState, build_agent_for_state, load_query_case
    from retroassist.config import AppConfig
    from retroassist.paths import fixtures_root
    from retroassist.speech.dialogue import VoiceDialogue
    from retroassist.speech.modes import SpeechModeController
    from retroassist.speech.stt import MockSpeechToText, create_stt, load_fixture_transcript
    from retroassist.speech.tts import create_tts
    from retroassist.vision.analyzer import frames_from_image_paths

    assert isinstance(cfg, AppConfig)
    if args.mode:
        cfg.raw.setdefault("speech", {})["mode"] = args.mode

    work = Path(args.state).parent if args.state else cfg.resolve_data_path("sessions")
    work.mkdir(parents=True, exist_ok=True)
    work_dir = work / ".listen-work"
    work_dir.mkdir(parents=True, exist_ok=True)

    state = SliceState(mock=bool(args.mock))
    image_path: Path | None = Path(args.image) if args.image else None

    if args.case:
        case = load_query_case(str(args.case).lower())
        state.vision_case = str(case.get("vision_case") or args.case)
        state.agent_case = str(case.get("agent_case") or args.case)
        state.kb_samples = [str(x) for x in (case.get("kb_samples") or [])]
        state.empty_kb = not bool(case.get("use_kb"))
        image_path = fixtures_root() / "images" / case["image"]
        agent = await build_agent_for_state(state, config=cfg, work_dir=work_dir)
        await agent.intake(str(case["symptom"]), str(case.get("visual_notes") or ""))
        default_transcript = str(case["query"])
    else:
        state.agent_case = args.agent_case
        agent = await build_agent_for_state(state, config=cfg, work_dir=work_dir)
        default_transcript = "What should I check next?"

    frames_provider = None
    if image_path is not None and image_path.is_file():

        def _frames() -> list:
            return frames_from_image_paths([str(image_path)])

        frames_provider = _frames

    tts = create_tts(cfg, force_mock=bool(args.mock))
    stt = create_stt(cfg, force_mock=bool(args.mock))
    dialogue = VoiceDialogue(
        agent=agent,
        stt=stt,
        tts=tts,
        modes=SpeechModeController.from_config(cfg, on_barge_in=tts.stop),
        config=cfg,
        look_now_frames_provider=frames_provider,
    )

    try:
        if args.transcript:
            result = await dialogue.handle_transcript(args.transcript)
        elif args.audio:
            audio_path = Path(args.audio)
            sidecar = audio_path.with_suffix(".json")
            if isinstance(stt, MockSpeechToText) and sidecar.is_file():
                stt.set_transcript(load_fixture_transcript(sidecar))
            audio_bytes = audio_path.read_bytes()
            result = await dialogue.handle_audio(audio_bytes)
        elif args.mock:
            # Default mock turn without mic
            result = await dialogue.handle_transcript(default_transcript)
        else:
            print(
                "Live mic listen requires audio hardware integration; "
                "use --transcript, --audio, or --mock for now.",
                file=sys.stderr,
            )
            return 2
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    def _out(line: str) -> None:
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
                sys.stdout.encoding or "utf-8", errors="replace"
            ))

    _out(f"intent: {result.intent.value}")
    _out(f"transcript: {result.transcript}")
    _out(f"spoken: {result.spoken_text}")
    _out(
        f"latency_ms: {result.latency_ms:.1f} "
        f"(target={dialogue.voice_target_seconds}s within={result.within_target})"
    )
    if result.suggestion:
        _out(f"action: {result.suggestion.get('action')}")
    if result.export_path:
        _out(f"export: {result.export_path}")
    return 0


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
