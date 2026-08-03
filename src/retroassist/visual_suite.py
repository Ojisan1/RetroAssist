"""Headless visual + agent regression suite (Phase 5.5 gate)."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from retroassist.agent.loop import DiagnosticAgent
from retroassist.agent.mock_llm import MockAgentLLM
from retroassist.agent.safety import rejects_fabricated_manual_citation, text_implies_high_risk
from retroassist.paths import fixtures_root, samples_knowledge_root
from retroassist.rag.embeddings import HashingEmbedder
from retroassist.rag.knowledge import LocalKnowledgeStore
from retroassist.vision.analyzer import WorkbenchVisionAnalyzer, frames_from_image_paths
from retroassist.vision.mock_store import MockLLMClient, MockVLMStore

# Gate minimum (execution-plan §6); --all expands to full Phase 5 suite.
BASIC_CASES = ("ps01", "meter01", "empty01", "nokb01")
ALL_CASES = ("ps01", "ps02", "logic01", "meter01", "empty01", "nokb01")


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    detail: str = ""
    latency_ms: float | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class SuiteReport:
    results: list[CaseResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.results) and all(r.passed for r in self.results)

    def summary_lines(self) -> list[str]:
        lines = ["RetroAssist visual+agent suite", ""]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lat = f" latency_ms={r.latency_ms:.1f}" if r.latency_ms is not None else ""
            lines.append(f"[{status}] {r.case_id}{lat}")
            if r.detail:
                lines.append(f"         {r.detail}")
            for err in r.errors:
                lines.append(f"         ERROR: {err}")
        lines.append("")
        passed = sum(1 for r in self.results if r.passed)
        status = "GREEN" if self.ok else "RED"
        lines.append(f"Result: {status} ({passed}/{len(self.results)})")
        return lines


def _load_query(stem: str) -> dict[str, Any]:
    path = fixtures_root() / "queries" / f"{stem}.json"
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Bad query fixture: {path}")
    return data


def _blob(suggestion: dict[str, Any], observation: dict[str, Any]) -> str:
    parts = [
        suggestion.get("action", ""),
        suggestion.get("expected_result", ""),
        suggestion.get("rationale", ""),
        " ".join(suggestion.get("safety_notes") or []),
        observation.get("summary", ""),
        str(observation.get("meter_reading") or ""),
    ]
    return " ".join(str(p) for p in parts).lower()


async def _build_agent(case: dict[str, Any], work_dir: Path) -> DiagnosticAgent:
    fixtures = fixtures_root()
    vision = WorkbenchVisionAnalyzer(
        MockLLMClient(
            MockVLMStore(fixtures / "vision" / "responses"),
            case_id=case["vision_case"],
        ),
        model="mock-vlm",
        latency_log_enabled=True,
    )
    if case.get("use_kb"):
        kb = LocalKnowledgeStore(work_dir / f"kb-{case['id']}", embedder=HashingEmbedder(96))
        samples = samples_knowledge_root()
        for name in case.get("kb_samples") or []:
            await kb.ingest(str(samples / name), metadata={"platform": "sample"})
    else:
        kb = LocalKnowledgeStore(work_dir / f"kb-empty-{case['id']}", embedder=HashingEmbedder(32))

    agent_llm = MockAgentLLM(fixtures / "agent" / "responses", case_id=case["agent_case"])
    return DiagnosticAgent(llm=agent_llm, vision=vision, knowledge=kb, model="mock-agent")


async def run_case(stem: str, *, work_dir: Path | None = None) -> CaseResult:
    """Execute one keyframe+query case against mocked VLM + MockAgentLLM."""
    own_tmp = work_dir is None
    tmp = Path(tempfile.mkdtemp(prefix="retroassist-suite-")) if own_tmp else work_dir
    assert tmp is not None
    errors: list[str] = []
    try:
        case = _load_query(stem)
        case_id = str(case.get("id") or stem.upper())
        agent = await _build_agent(case, tmp)
        await agent.intake(case["symptom"], case.get("visual_notes", ""))
        image = fixtures_root() / "images" / case["image"]
        if not image.is_file():
            return CaseResult(case_id=case_id, passed=False, errors=[f"missing image {image}"])
        frames = frames_from_image_paths([str(image)])
        observation = await agent.look_now(frames)
        suggestion = await agent.ask(case["query"])
        expect = case.get("expect") or {}
        blob = _blob(suggestion, observation)

        needles = expect.get("must_include_any") or []
        if needles and not any(n.lower() in blob for n in needles):
            errors.append(f"missing any of {needles}")

        if expect.get("board_visible") is False and observation.get("board_visible") is not False:
            errors.append("expected board_visible=False")

        if expect.get("acknowledge_meter"):
            if not (
                observation.get("meter_reading") or "0.00" in blob or "zero" in blob
            ):
                errors.append("did not acknowledge meter reading")

        if expect.get("safety_mains"):
            joined = " ".join(suggestion.get("safety_notes") or [])
            if not (text_implies_high_risk(joined) or "responsible" in joined.lower()):
                errors.append("missing mains/HV safety framing")

        if expect.get("citations_required") and not suggestion.get("citations"):
            errors.append("expected retrieval citations")

        if expect.get("kb_empty") or expect.get("no_fabricated_citations"):
            if suggestion.get("kb_empty") is not True:
                errors.append("expected kb_empty=True")
            if suggestion.get("citations"):
                errors.append("expected no citations on empty KB")
            for key in ("action", "rationale", "expected_result"):
                if rejects_fabricated_manual_citation(str(suggestion.get(key) or "")):
                    errors.append(f"fabricated manual citation in {key}")

        md = agent.export_markdown()
        for required in (case["symptom"], "## Suggestions", "## Intake"):
            if required not in md:
                errors.append(f"export missing {required!r}")
        if not agent.session.latency_notes:
            errors.append("export path missing latency_notes")

        latency = observation.get("latency_ms")
        latency_f = float(latency) if latency is not None else None
        detail = (observation.get("summary") or "")[:80]
        return CaseResult(
            case_id=case_id,
            passed=not errors,
            detail=detail,
            latency_ms=latency_f,
            errors=errors,
        )
    except Exception as exc:  # noqa: BLE001 — suite reports failures, does not crash
        return CaseResult(case_id=stem.upper(), passed=False, errors=[str(exc)])
    finally:
        if own_tmp:
            # Best-effort cleanup; chroma lock files may linger briefly on Windows.
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)


async def run_suite(
    cases: list[str] | tuple[str, ...] | None = None,
    *,
    work_dir: Path | None = None,
) -> SuiteReport:
    """Run mocked visual+agent cases; default = Phase 5.5 basic gate set."""
    selected = list(cases) if cases is not None else list(BASIC_CASES)
    report = SuiteReport()
    for stem in selected:
        if work_dir is not None:
            case_dir = work_dir / stem
            case_dir.mkdir(parents=True, exist_ok=True)
            result = await run_case(stem, work_dir=case_dir)
        else:
            result = await run_case(stem)
        report.results.append(result)
    return report


def resolve_case_list(
    *,
    basic: bool = True,
    all_cases: bool = False,
    cases: str | None = None,
) -> list[str]:
    if cases:
        return [c.strip().lower() for c in cases.split(",") if c.strip()]
    if all_cases:
        return list(ALL_CASES)
    if basic:
        return list(BASIC_CASES)
    return list(BASIC_CASES)
