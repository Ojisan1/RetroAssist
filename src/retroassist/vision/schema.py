"""Structured vision observation schema and parsing."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ParseStatus = Literal["structured", "free_text_fallback", "empty"]


@dataclass
class VisionObservation:
    """Structured (or fallback) observation from workbench imagery."""

    summary: str
    board_visible: bool | None = None
    components: list[str] = field(default_factory=list)
    tools_or_meters: list[str] = field(default_factory=list)
    damage_or_anomalies: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    meter_reading: str | None = None
    parse_status: ParseStatus = "structured"
    raw_text: str = ""
    model: str = ""
    latency_ms: float | None = None
    latency_target_seconds: float | None = None
    latency_within_target: bool | None = None
    analysis_id: int = 0
    superseded: bool = False
    source_ids: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def parse_observation_text(text: str, *, model: str = "") -> VisionObservation:
    """Parse model output into a VisionObservation (JSON preferred, free-text fallback)."""
    raw = (text or "").strip()
    if not raw:
        return VisionObservation(
            summary="",
            parse_status="empty",
            raw_text="",
            model=model,
            uncertainties=["Model returned empty vision output."],
        )

    candidate = _extract_json_candidate(raw)
    if candidate is not None:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return _from_mapping(data, raw_text=raw, model=model, status="structured")
        except json.JSONDecodeError:
            pass

    return VisionObservation(
        summary=raw[:2000],
        parse_status="free_text_fallback",
        raw_text=raw,
        model=model,
        uncertainties=["Could not parse structured JSON; using free-text summary."],
    )


def _extract_json_candidate(text: str) -> str | None:
    fence = _JSON_FENCE.search(text)
    if fence:
        return fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return None


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        item = value.strip()
        return [item] if item else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value)]


def _from_mapping(
    data: dict[str, Any],
    *,
    raw_text: str,
    model: str,
    status: ParseStatus,
) -> VisionObservation:
    board = data.get("board_visible")
    board_visible: bool | None
    if board is None:
        board_visible = None
    else:
        board_visible = bool(board)

    summary = str(data.get("summary") or data.get("observation") or "").strip()
    if not summary:
        summary = raw_text[:500]

    meter = data.get("meter_reading")
    meter_reading = None if meter is None else str(meter)

    return VisionObservation(
        summary=summary,
        board_visible=board_visible,
        components=_as_str_list(data.get("components")),
        tools_or_meters=_as_str_list(data.get("tools_or_meters") or data.get("tools")),
        damage_or_anomalies=_as_str_list(
            data.get("damage_or_anomalies") or data.get("anomalies")
        ),
        uncertainties=_as_str_list(data.get("uncertainties")),
        meter_reading=meter_reading,
        parse_status=status,
        raw_text=raw_text,
        model=model,
    )
