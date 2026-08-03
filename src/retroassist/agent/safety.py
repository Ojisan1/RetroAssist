"""Safety framing for HV / CRT / mains-adjacent guidance."""

from __future__ import annotations

import re
from typing import Any

MAINS_HV_PATTERNS = (
    r"\bmains\b",
    r"\bline\s*voltage\b",
    r"\bhigh[\s-]?voltage\b",
    r"\bhv\b",
    r"\bcrt\b",
    r"\bfuse\b",
    r"\bpsu\b",
    r"\bpower\s+supply\b",
    r"\bno\s+power\b",
    r"\bcapacitor\s+discharge\b",
    r"\bdischarge\b",
)

DEFAULT_CAUTION = (
    "Exercise caution: this may involve mains / high voltage. "
    "Confirm the equipment is unplugged and capacitors are safely discharged "
    "before probing. Verify critical steps against primary documentation; "
    "you remain fully responsible for all actions."
)


def text_implies_high_risk(text: str) -> bool:
    blob = (text or "").lower()
    return any(re.search(pat, blob) for pat in MAINS_HV_PATTERNS)


def context_implies_high_risk(
    *,
    symptom: str = "",
    visual_notes: str = "",
    observation_summary: str = "",
    query: str = "",
) -> bool:
    joined = " ".join([symptom, visual_notes, observation_summary, query])
    return text_implies_high_risk(joined)


def ensure_safety_notes(
    suggestion: dict[str, Any],
    *,
    high_risk: bool,
    require_framing: bool = True,
) -> dict[str, Any]:
    """Ensure cautionary framing is present when the scenario is high-risk."""
    out = dict(suggestion)
    notes = list(out.get("safety_notes") or [])
    if high_risk and require_framing:
        if not any(text_implies_high_risk(n) or "responsible" in n.lower() for n in notes):
            notes.insert(0, DEFAULT_CAUTION)
        # Soften authoritative tone markers if present
        action = str(out.get("action") or "")
        action = re.sub(r"^\s*you must\b", "Consider", action, flags=re.IGNORECASE)
        out["action"] = action
    out["safety_notes"] = notes
    out["high_risk"] = high_risk
    return out


def rejects_fabricated_manual_citation(text: str) -> bool:
    """Heuristic: flag claims that invent specific manual pages without retrieval."""
    patterns = (
        r"manual\s+page\s+\d+",
        r"see\s+page\s+\d+\s+of\s+the\s+service\s+manual",
        r"schematic\s+sheet\s+\d+",
    )
    lowered = text.lower()
    return any(re.search(p, lowered) for p in patterns)
