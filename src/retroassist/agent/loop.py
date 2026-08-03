"""Agent loop: intake + vision + RAG → grounded next steps."""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any, Protocol

from retroassist.agent.context import build_context_bundle, remember_step
from retroassist.agent.export import export_session_markdown, session_to_markdown
from retroassist.agent.intake import IntakeError, apply_intake
from retroassist.agent.prompts import SYSTEM_PROMPT, build_suggestion_prompt, parse_suggestion_text
from retroassist.agent.safety import (
    context_implies_high_risk,
    ensure_safety_notes,
    rejects_fabricated_manual_citation,
)
from retroassist.agent.session import DiagnosticSession
from retroassist.capture.base import EncodedFrame, Frame
from retroassist.config import AppConfig
from retroassist.interfaces import AgentLoop, KnowledgeStore, VisionAnalyzer


class SupportsChat(Protocol):
    async def chat(
        self,
        messages: Sequence[Any],
        *,
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> Any: ...


class DiagnosticAgent(AgentLoop):
    """Text-first diagnostic agent fusing vision, RAG, memory, and safety."""

    def __init__(
        self,
        *,
        llm: SupportsChat,
        vision: VisionAnalyzer | None = None,
        knowledge: KnowledgeStore | None = None,
        model: str = "mock-agent",
        session: DiagnosticSession | None = None,
        require_safety_framing: bool = True,
        strip_fabricated_citations_when_empty_kb: bool = True,
    ) -> None:
        self.llm = llm
        self.vision = vision
        self.knowledge = knowledge
        self.model = model
        self.session = session or DiagnosticSession()
        self.require_safety_framing = require_safety_framing
        self.strip_fabricated_citations_when_empty_kb = strip_fabricated_citations_when_empty_kb
        self._last_query: str = ""

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        llm: SupportsChat,
        vision: VisionAnalyzer | None = None,
        knowledge: KnowledgeStore | None = None,
    ) -> DiagnosticAgent:
        models = config.resolved_models()
        safety = config.safety_flags
        return cls(
            llm=llm,
            vision=vision,
            knowledge=knowledge,
            model=models["llm"],
            require_safety_framing=bool(safety.get("include_cautionary_framing", True)),
        )

    async def intake(self, symptom: str, visual_notes: str = "") -> None:
        apply_intake(self.session, symptom, visual_notes)

    async def look_now(
        self,
        frames: Sequence[Frame | EncodedFrame | Any],
        *,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        if self.vision is None:
            raise RuntimeError("No vision analyzer configured for look_now()")
        started = time.perf_counter()
        if hasattr(self.vision, "analyze_frames"):
            observation = await self.vision.analyze_frames(frames, prompt=prompt)  # type: ignore[attr-defined]
            payload = (
                observation.to_dict()
                if hasattr(observation, "to_dict")
                else dict(observation)
            )
        else:
            payload = await self.vision.analyze(frames, prompt=prompt)
        latency_ms = (time.perf_counter() - started) * 1000.0
        if payload.get("latency_ms") is None:
            payload["latency_ms"] = latency_ms
        self.session.observations.append(payload)
        self.session.latency_notes.append(
            {
                "timestamp": time.time(),
                "label": "look_now",
                "latency_ms": payload.get("latency_ms", latency_ms),
            }
        )
        self.session.record(
            "look_now",
            {
                "summary": payload.get("summary"),
                "latency_ms": payload.get("latency_ms"),
            },
        )
        return payload

    async def suggest_next(self) -> dict[str, Any]:
        query = self._last_query or (
            self.session.intake.symptom if self.session.intake else "What should I check next?"
        )
        return await self._suggest(query=query)

    async def report_measurement(self, text: str) -> dict[str, Any]:
        cleaned = (text or "").strip()
        if not cleaned:
            raise IntakeError("Measurement report must be non-empty.")
        item = {"text": cleaned, "timestamp": time.time()}
        self.session.measurements.append(item)
        self.session.record("measurement", item)
        return await self._suggest(query=cleaned)

    async def ask(self, query: str) -> dict[str, Any]:
        """Free-form technician query → next-step suggestion."""
        self._last_query = (query or "").strip()
        return await self._suggest(query=self._last_query)

    def export_markdown(self) -> str:
        return session_to_markdown(self.session)

    def export_to_path(self, path: str) -> str:
        export_session_markdown(self.session, path)
        return path

    async def _suggest(self, *, query: str) -> dict[str, Any]:
        obs = self.session.observations[-1] if self.session.observations else {}
        obs_summary = str(obs.get("summary") or "")

        hits: list[dict[str, Any]] = []
        kb_empty = True
        if self.knowledge is not None:
            hits = await self.knowledge.retrieve(
                query or (self.session.intake.symptom if self.session.intake else ""),
                limit=5,
                vision_summary=obs_summary or None,
            )
            kb_empty = self.knowledge.count == 0 if hasattr(self.knowledge, "count") else not hits
            # If count API exists and is 0, trust empty even if somehow hits
            if hasattr(self.knowledge, "count") and self.knowledge.count == 0:
                hits = []
                kb_empty = True
        self.session.retrievals.append(
            {"query": query, "hits": hits, "timestamp": time.time(), "kb_empty": kb_empty}
        )
        self.session.record(
            "retrieve",
            {"query": query, "hit_count": len(hits), "kb_empty": kb_empty},
        )

        bundle = build_context_bundle(self.session, query=query, retrieval_hits=hits)
        prompt = build_suggestion_prompt(bundle)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        result = await self.llm.chat(messages, model=self.model)
        content = result.content if hasattr(result, "content") else str(result)
        suggestion = parse_suggestion_text(content)

        high_risk = context_implies_high_risk(
            symptom=bundle.get("symptom", ""),
            visual_notes=bundle.get("visual_notes", ""),
            observation_summary=obs_summary,
            query=query,
        )
        suggestion = ensure_safety_notes(
            suggestion,
            high_risk=high_risk,
            require_framing=self.require_safety_framing,
        )

        # Ground citations: if KB empty, strip fabricated manual citations
        if kb_empty and self.strip_fabricated_citations_when_empty_kb:
            suggestion["citations"] = []
            suggestion["kb_empty"] = True
            # Scrub rationale/action that invent pages
            for key in ("action", "rationale", "expected_result"):
                val = str(suggestion.get(key) or "")
                if rejects_fabricated_manual_citation(val):
                    suggestion[key] = (
                        "Use general electronics knowledge and the live visual observation; "
                        "no local manual is loaded, so do not cite specific manual pages."
                    )
        else:
            suggestion["kb_empty"] = False
            # Prefer attaching retrieval hits as citations when model omitted them
            if hits and not suggestion.get("citations"):
                suggestion["citations"] = [
                    {
                        "source": h.get("source"),
                        "page": h.get("page"),
                        "excerpt": (h.get("text") or "")[:240],
                    }
                    for h in hits[:3]
                ]

        suggestion["timestamp"] = time.time()
        suggestion["query"] = query
        remember_step(self.session, str(suggestion.get("action") or ""))
        for tag in suggestion.get("task_tags") or []:
            if tag not in self.session.task_tags:
                self.session.task_tags.append(str(tag))
        self.session.suggestions.append(suggestion)
        self.session.record("suggestion", {"action": suggestion.get("action")})
        return suggestion
