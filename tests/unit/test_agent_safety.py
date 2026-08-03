"""Safety framing unit tests."""

from retroassist.agent.safety import (
    DEFAULT_CAUTION,
    context_implies_high_risk,
    ensure_safety_notes,
    rejects_fabricated_manual_citation,
    text_implies_high_risk,
)


def test_mains_and_fuse_detected() -> None:
    assert text_implies_high_risk("Check the mains fuse first")
    assert context_implies_high_risk(symptom="No power", observation_summary="PSU fuse area")


def test_benign_logic_not_flagged() -> None:
    assert not text_implies_high_risk("Check the clock oscillator near U12")


def test_ensure_safety_notes_injects_caution() -> None:
    sug = {"action": "You must probe the fuse.", "safety_notes": []}
    out = ensure_safety_notes(sug, high_risk=True, require_framing=True)
    assert out["high_risk"] is True
    assert any("responsible" in n.lower() or "mains" in n.lower() for n in out["safety_notes"])
    assert DEFAULT_CAUTION.split()[0] in " ".join(out["safety_notes"])
    assert not out["action"].lower().startswith("you must")


def test_fabricated_manual_page_detector() -> None:
    assert rejects_fabricated_manual_citation("See page 42 of the service manual")
    assert not rejects_fabricated_manual_citation("Check continuity with a meter")
