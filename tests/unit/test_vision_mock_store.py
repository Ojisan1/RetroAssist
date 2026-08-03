"""Tests for mocked VLM response store."""

from pathlib import Path

from retroassist.vision.mock_store import MockVLMStore

RESPONSES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "vision" / "responses"
)


def test_mock_store_lists_cases() -> None:
    store = MockVLMStore(RESPONSES)
    cases = store.list_cases()
    assert "empty_bench" in cases
    assert "meter_readings" in cases
    assert "power_supply" in cases
    assert "logic_board" in cases


def test_mock_store_response_text_roundtrip() -> None:
    store = MockVLMStore(RESPONSES)
    text = store.response_text("empty_bench")
    assert "board_visible" in text
    assert "Empty workbench" in text or "empty" in text.lower()
