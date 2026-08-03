"""Doctor and operational checks for the local environment."""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path

from retroassist import __version__
from retroassist.config import AppConfig, load_config, platform_config_dir
from retroassist.llm.client import LLMClient, LLMUnavailableError


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
        report.add("speech", True, f"mode={mode}")
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

    _add_capture_checks(report, cfg)

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
