"""Unit tests for hardware-tier model profiles."""

import pytest

from retroassist.llm.models import (
    MODEL_PROFILES,
    VALID_TIERS,
    get_profile,
    resolve_model_names,
)


def test_all_tiers_defined() -> None:
    assert set(MODEL_PROFILES) == set(VALID_TIERS)
    for tier in VALID_TIERS:
        profile = get_profile(tier)
        assert profile.llm
        assert profile.vision
        assert profile.embedding
        assert profile.vram_gb_min >= 12


def test_get_profile_aliases() -> None:
    assert get_profile("recommended").tier == "recommended"
    assert get_profile("usable").tier == "entry"
    assert get_profile("high-end").tier == "high_end"


def test_get_profile_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown hardware tier"):
        get_profile("toaster")


def test_resolve_model_names_overrides() -> None:
    resolved = resolve_model_names(
        "entry",
        llm="my-llm",
        vision=None,
        embedding="my-embed",
    )
    assert resolved["tier"] == "entry"
    assert resolved["llm"] == "my-llm"
    assert resolved["embedding"] == "my-embed"
    assert resolved["vision"] == get_profile("entry").vision


def test_vram_ranges_are_ordered() -> None:
    entry = get_profile("entry")
    recommended = get_profile("recommended")
    high = get_profile("high_end")
    assert entry.vram_gb_min < recommended.vram_gb_min <= high.vram_gb_min
    assert high.vram_gb_max is None
