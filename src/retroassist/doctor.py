"""Doctor and operational checks for the local environment."""

from __future__ import annotations

import platform
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from retroassist import __version__
from retroassist.config import AppConfig, load_config, platform_config_dir
from retroassist.llm.client import LLMClient, LLMUnavailableError

# Warn / fail install verification when free space on data volume is below this.
DISK_MIN_FREE_BYTES = 1 * 1024 * 1024 * 1024  # 1 GiB


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass
class DoctorReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append(CheckResult(name=name, ok=ok, detail=detail))


async def run_doctor(
    config: AppConfig | None = None,
    *,
    client: LLMClient | None = None,
    check_llm: bool = True,
) -> DoctorReport:
    """Run foundation health checks. ``client`` may be injected for tests."""
    report = DoctorReport()
    cfg = config or load_config()

    py_ok = sys.version_info >= (3, 11)
    report.add(
        "python",
        py_ok,
        f"{platform.python_version()} ({'ok' if py_ok else 'need 3.11+'})",
    )
    report.add("retroassist", True, f"version {__version__}")
    report.add("platform_config_dir", True, str(platform_config_dir()))

    if cfg.sources_loaded:
        loaded = ", ".join(str(p) for p in cfg.sources_loaded)
        report.add("config", True, f"loaded from: {loaded}")
    else:
        report.add("config", True, "using built-in defaults (no config.yaml found)")

    try:
        models = cfg.resolved_models()
        report.add(
            "models",
            True,
            (
                f"tier={models['tier']} llm={models['llm']} "
                f"vision={models['vision']} embedding={models['embedding']}"
            ),
        )
    except ValueError as exc:
        report.add("models", False, str(exc))
        models = None

    try:
        mode = cfg.speech_mode
        settings = cfg.speech_settings
        report.add(
            "speech",
            True,
            (
                f"mode={mode} stt={settings.get('stt_provider')} "
                f"tts={settings.get('tts_provider')} "
                f"cloud_opt_in={settings.get('cloud_opt_in')}"
            ),
        )
        _add_speech_engine_checks(report, cfg)
    except ValueError as exc:
        report.add("speech", False, str(exc))

    safety = cfg.safety_flags
    report.add(
        "safety",
        True,
        (
            f"hv_confirm={safety['require_human_confirmation_on_hv']} "
            f"cautionary_framing={safety['include_cautionary_framing']}"
        ),
    )
    report.add(
        "latency",
        True,
        f"log_enabled={cfg.latency_log_enabled}",
    )

    for key in ("knowledge_base", "sessions", "cache"):
        path = cfg.resolve_data_path(key)
        report.add(f"data_dir.{key}", True, str(path))

    _add_disk_checks(report, cfg)
    _add_capture_checks(report, cfg)
    _add_rag_checks(report, cfg)

    if check_llm:
        own_client = client is None
        llm = client or LLMClient(
            base_url=cfg.llm_base_url,
            api_key=cfg.llm_api_key,
            timeout_seconds=min(cfg.llm_timeout_seconds, 10.0),
        )
        try:
            names = await llm.list_models()
            preview = ", ".join(names[:8]) if names else "(none listed)"
            if len(names) > 8:
                preview += ", …"
            report.add("llm", True, f"reachable; models: {preview}")
            if models is not None:
                missing = [
                    models[key]
                    for key in ("llm", "vision", "embedding")
                    if not _model_present(models[key], names)
                ]
                if names and missing:
                    report.add(
                        "llm.models_pulled",
                        False,
                        "configured models not found on server: " + ", ".join(missing),
                    )
                elif names:
                    report.add("llm.models_pulled", True, "configured model names appear installed")
        except LLMUnavailableError as exc:
            report.add("llm", False, str(exc))
        finally:
            if own_client:
                await llm.aclose()

    return report


def _add_disk_checks(report: DoctorReport, cfg: AppConfig) -> None:
    """Validate free space on the volume hosting knowledge/sessions/cache."""
    paths = [cfg.resolve_data_path(k) for k in ("knowledge_base", "sessions", "cache")]
    # Prefer an existing ancestor so disk_usage works before dirs exist.
    probe = next((p for p in paths if p.exists()), None)
    if probe is None:
        probe = paths[0]
        for ancestor in [probe, *probe.parents]:
            if ancestor.exists():
                probe = ancestor
                break

    try:
        usage = shutil.disk_usage(probe)
    except OSError as exc:
        report.add("disk", False, f"unable to read free space at {probe}: {exc}")
        return

    free_gib = usage.free / (1024**3)
    total_gib = usage.total / (1024**3)
    ok = usage.free >= DISK_MIN_FREE_BYTES
    detail = f"{free_gib:.1f} GiB free of {total_gib:.1f} GiB at {probe}"
    if not ok:
        detail += f" (need >= {DISK_MIN_FREE_BYTES / (1024**3):.0f} GiB free)"
    report.add("disk", ok, detail)


def _add_capture_checks(report: DoctorReport, cfg: AppConfig) -> None:
    """Non-fatal capture backend + device enumeration."""
    try:
        import cv2  # noqa: F401

        from retroassist.capture.opencv_source import enumerate_devices
    except Exception as exc:  # noqa: BLE001 - doctor must stay resilient
        report.add("capture", False, f"OpenCV unavailable: {exc}")
        return

    report.add("capture", True, "opencv-python-headless import ok")
    # Keep doctor snappy: fewer indices, skip frame probe (open check only).
    max_index = min(4, int((cfg.raw.get("cameras") or {}).get("enumerate_max_index", 10)))
    try:
        devices = enumerate_devices(max_index=max_index, probe_frame=False)
    except Exception as exc:  # noqa: BLE001
        report.add("capture.devices", True, f"enumeration skipped: {exc}")
        return

    configured = cfg.camera_sources()
    if not devices:
        detail = "no cameras found (zero-camera / fixture mode still OK for CI)"
        if configured:
            detail += f"; config lists {len(configured)} source(s)"
        report.add("capture.devices", True, detail)
        return

    preview = ", ".join(f"{d.index}:{d.name}" for d in devices[:8])
    if len(devices) > 8:
        preview += ", …"
    report.add("capture.devices", True, preview)


def _add_rag_checks(report: DoctorReport, cfg: AppConfig) -> None:
    """Report knowledge-base path and chunk count (empty is OK)."""
    rag = cfg.raw.get("rag") or {}
    provider = str(rag.get("embedding_provider", "hashing"))
    kb_root = cfg.resolve_data_path("knowledge_base")
    persist = rag.get("persist_dir")
    if persist:
        persist_dir = Path(str(persist)).expanduser()
        if not persist_dir.is_absolute():
            persist_dir = cfg.config_dir / persist_dir
    else:
        persist_dir = kb_root / "chroma"

    try:
        from retroassist.rag.knowledge import LocalKnowledgeStore

        store = LocalKnowledgeStore.from_config(cfg)
        count = store.count
        report.add(
            "rag",
            True,
            f"provider={provider} chunks={count} path={persist_dir}",
        )
        if count == 0:
            report.add(
                "rag.empty",
                True,
                "knowledge base empty (NO-KB / graceful degradation OK)",
            )
    except Exception as exc:  # noqa: BLE001
        report.add("rag", True, f"KB path {persist_dir} (init deferred: {exc})")


def _add_speech_engine_checks(report: DoctorReport, cfg: AppConfig) -> None:
    """Optional STT/TTS backend availability (non-fatal if mock-only)."""
    settings = cfg.speech_settings
    stt = str(settings.get("stt_provider", "mock")).lower()
    tts = str(settings.get("tts_provider", "mock")).lower()

    if stt == "whisper":
        try:
            import faster_whisper  # noqa: F401

            report.add(
                "speech.stt",
                True,
                f"faster-whisper ok (model={settings.get('whisper_model')})",
            )
        except ImportError:
            report.add(
                "speech.stt",
                False,
                "stt_provider=whisper but faster-whisper missing; "
                "optional: pip install 'retroassist[speech]'",
            )
    else:
        report.add("speech.stt", True, f"provider={stt} (CI/mock ok without live mic)")

    if tts == "piper":
        voice = settings.get("piper_voice_model")
        if voice and Path(str(voice)).is_file():
            report.add("speech.tts", True, f"piper voice present: {voice}")
        else:
            report.add(
                "speech.tts",
                False,
                "tts_provider=piper requires speech.piper_voice_model path to an .onnx file",
            )
    else:
        report.add("speech.tts", True, f"provider={tts}")

    if settings.get("cloud_opt_in"):
        url = settings.get("cloud_stt_url")
        report.add(
            "speech.cloud",
            bool(url),
            "cloud_opt_in enabled" + (f"; url={url}" if url else "; cloud_stt_url missing"),
        )


def _model_present(wanted: str, available: list[str]) -> bool:
    """Loose match: exact, prefix before ':', or substring."""
    if not available:
        # Empty listing — cannot assert; treat as inconclusive/pass at this check.
        return True
    wanted_l = wanted.lower()
    for name in available:
        n = name.lower()
        if n == wanted_l or n.startswith(wanted_l) or wanted_l in n:
            return True
    return False


def format_report(report: DoctorReport) -> str:
    lines = ["RetroAssist doctor", "=================="]
    for check in report.checks:
        mark = "OK" if check.ok else "FAIL"
        lines.append(f"[{mark}] {check.name}: {check.detail}")
    lines.append("")
    lines.append("Overall: " + ("PASS" if report.ok else "FAIL"))
    return "\n".join(lines)


def ensure_platform_dirs(config: AppConfig | None = None) -> list[Path]:
    """Create platform config + default data directories. Returns paths created/ensured."""
    cfg = config or load_config()
    paths = [cfg.config_dir]
    paths.extend(cfg.resolve_data_path(k) for k in ("knowledge_base", "sessions", "cache"))
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    return paths
