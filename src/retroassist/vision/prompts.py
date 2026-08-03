"""Multimodal prompts for electronics workbench vision analysis."""

from __future__ import annotations

from collections.abc import Sequence

SYSTEM_PROMPT = """You are RetroAssist vision, a careful observer for classic electronics repair.
Describe only what is visible in the provided workbench image(s).
Do not invent schematic page numbers or part designations you cannot see.
Prefer uncertainty over guessing. The human remains responsible for all actions.
Respond with a single JSON object (no markdown) using this schema:
{
  "summary": "string",
  "board_visible": true/false,
  "components": ["string"],
  "tools_or_meters": ["string"],
  "damage_or_anomalies": ["string"],
  "meter_reading": "string or null",
  "uncertainties": ["string"]
}
"""


def build_user_prompt(
    *,
    extra_prompt: str | None = None,
    roles: Sequence[str] | None = None,
) -> str:
    """Build the text portion of a multimodal user message."""
    role_list = list(roles or [])
    lines = [
        "Analyze these electronics workbench frame(s).",
    ]
    if role_list:
        labeled = ", ".join(f"{idx + 1}={role}" for idx, role in enumerate(role_list))
        lines.append(f"Image roles in order: {labeled}.")
        if "overview" in role_list and "close_up" in role_list:
            lines.append(
                "Use the overview for context and the close-up for fine detail "
                "(probe tip, meter display, component markings)."
            )
    lines.append(
        "Focus on: board presence, visible components, meters/tools, damage or anomalies, "
        "and any readable meter values."
    )
    if extra_prompt:
        lines.append(extra_prompt.strip())
    lines.append("Return JSON only.")
    return "\n".join(lines)
