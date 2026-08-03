"""Model profiles keyed by GPU VRAM tier (ProjectSpec §7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HardwareTier = Literal["entry", "recommended", "high_end"]

VALID_TIERS: tuple[HardwareTier, ...] = ("entry", "recommended", "high_end")


@dataclass(frozen=True)
class ModelProfile:
    """Default Ollama model tags for a hardware tier."""

    tier: HardwareTier
    vram_gb_min: int
    vram_gb_max: int | None
    llm: str
    vision: str
    embedding: str
    description: str


# Profiles use commonly available Ollama tags as sensible starting points.
# Users may override names in config; exact tags will evolve with testing.
MODEL_PROFILES: dict[HardwareTier, ModelProfile] = {
    "entry": ModelProfile(
        tier="entry",
        vram_gb_min=12,
        vram_gb_max=16,
        llm="qwen2.5:7b",
        vision="qwen2.5vl:7b",
        embedding="nomic-embed-text",
        description="Quantized / smaller models for 12–16 GB VRAM (usable frame analysis).",
    ),
    "recommended": ModelProfile(
        tier="recommended",
        vram_gb_min=24,
        vram_gb_max=31,
        llm="qwen2.5:14b",
        vision="qwen2.5vl:11b",
        embedding="nomic-embed-text",
        description="Larger VLMs for smoother multi-image and longer context (~24 GB).",
    ),
    "high_end": ModelProfile(
        tier="high_end",
        vram_gb_min=32,
        vram_gb_max=None,
        llm="qwen2.5:32b",
        vision="qwen2.5vl:32b",
        embedding="nomic-embed-text",
        description="Maximum quality and headroom (32 GB+ VRAM).",
    ),
}


def get_profile(tier: str) -> ModelProfile:
    """Return the model profile for a tier name."""
    key = tier.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "entry": "entry",
        "usable": "entry",
        "entry_usable": "entry",
        "recommended": "recommended",
        "high": "high_end",
        "high_end": "high_end",
        "highend": "high_end",
    }
    mapped = aliases.get(key)
    if mapped is None or mapped not in MODEL_PROFILES:
        valid = ", ".join(VALID_TIERS)
        raise ValueError(f"Unknown hardware tier {tier!r}; expected one of: {valid}")
    return MODEL_PROFILES[mapped]  # type: ignore[index]


def resolve_model_names(
    tier: str,
    *,
    llm: str | None = None,
    vision: str | None = None,
    embedding: str | None = None,
) -> dict[str, str]:
    """Resolve effective model names from tier defaults plus optional overrides."""
    profile = get_profile(tier)
    return {
        "tier": profile.tier,
        "llm": llm or profile.llm,
        "vision": vision or profile.vision,
        "embedding": embedding or profile.embedding,
    }
