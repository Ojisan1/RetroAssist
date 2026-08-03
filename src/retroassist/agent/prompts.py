"""Prompts and parsing for grounded next-step suggestions."""

from __future__ import annotations

import json
import re
from typing import Any

from retroassist.agent.context import format_hits_for_prompt

SYSTEM_PROMPT = """You are RetroAssist, a diagnostic assistant for skilled electronics technicians.
Propose concrete next checks grounded in the session intake, visual observation, and retrieved docs.
Never invent service-manual page numbers or schematic citations that were not retrieved.
If the knowledge base is empty, say so and use general electronics + vision only.
You remain advisory; the human is fully responsible. Prefer caution on mains/HV/CRT work.
Return a single JSON object:
{
  "action": "string",
  "expected_result": "string",
  "rationale": "string",
  "confidence": 0.0,
  "safety_notes": ["string"],
  "citations": [{"source": "string", "page": null, "excerpt": "string"}],
  "task_tags": ["diagnosis"|"longevity"|"modification"]
}
"""


def build_suggestion_prompt(bundle: dict[str, Any]) -> str:
    obs = bundle.get("observation") or {}
    obs_summary = obs.get("summary") if isinstance(obs, dict) else ""
    hits = bundle.get("retrieval_hits") or []
    lines = [
        f"Symptom: {bundle.get('symptom', '')}",
        f"Visual notes: {bundle.get('visual_notes', '')}",
        f"Technician query: {bundle.get('query', '')}",
        f"Vision summary: {obs_summary}",
        f"Meter reading (if any): {obs.get('meter_reading') if isinstance(obs, dict) else None}",
        f"Steps already tried: {', '.join(bundle.get('steps_tried') or []) or '(none)'}",
        f"Recent measurements: {bundle.get('measurements') or []}",
        f"Task tags: {bundle.get('task_tags') or []}",
        "Retrieved documentation:",
        format_hits_for_prompt(list(hits)),
        "Propose the single best next diagnostic step as JSON.",
    ]
    return "\n".join(lines)


_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def parse_suggestion_text(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    candidate = _extract_json(raw)
    if candidate:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return _normalize_suggestion(data, raw_text=raw)
        except json.JSONDecodeError:
            pass
    return _normalize_suggestion(
        {
            "action": raw[:500] or "Clarify the symptom and repeat visual inspection.",
            "expected_result": "",
            "rationale": "Model did not return structured JSON; using free-text fallback.",
            "confidence": 0.3,
            "safety_notes": [],
            "citations": [],
            "task_tags": ["diagnosis"],
        },
        raw_text=raw,
    )


def _extract_json(text: str) -> str | None:
    fence = _JSON_FENCE.search(text)
    if fence:
        return fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return None


def _normalize_suggestion(data: dict[str, Any], *, raw_text: str) -> dict[str, Any]:
    citations_in = data.get("citations") or []
    citations: list[dict[str, Any]] = []
    if isinstance(citations_in, list):
        for item in citations_in:
            if isinstance(item, dict):
                citations.append(
                    {
                        "source": item.get("source"),
                        "page": item.get("page"),
                        "excerpt": item.get("excerpt") or item.get("text"),
                    }
                )
            elif isinstance(item, str) and item.strip():
                citations.append({"source": item, "page": None, "excerpt": None})

    safety = data.get("safety_notes") or []
    if isinstance(safety, str):
        safety_notes = [safety]
    else:
        safety_notes = [str(s) for s in safety if str(s).strip()]

    tags = data.get("task_tags") or ["diagnosis"]
    if isinstance(tags, str):
        tags = [tags]

    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5

    return {
        "action": str(data.get("action") or "").strip()
        or "Clarify the symptom and inspect the board carefully.",
        "expected_result": str(data.get("expected_result") or "").strip(),
        "rationale": str(data.get("rationale") or "").strip(),
        "confidence": max(0.0, min(1.0, confidence)),
        "safety_notes": safety_notes,
        "citations": citations,
        "task_tags": [str(t) for t in tags],
        "raw_text": raw_text,
    }
