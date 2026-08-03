"""Tests for vision observation parsing."""

from retroassist.vision.schema import parse_observation_text


def test_parse_structured_json() -> None:
    text = """
    {
      "summary": "Board present",
      "board_visible": true,
      "components": ["capacitor"],
      "tools_or_meters": ["probe"],
      "damage_or_anomalies": ["burn mark"],
      "meter_reading": null,
      "uncertainties": ["angle"]
    }
    """
    obs = parse_observation_text(text, model="test")
    assert obs.parse_status == "structured"
    assert obs.board_visible is True
    assert obs.components == ["capacitor"]
    assert obs.tools_or_meters == ["probe"]
    assert obs.model == "test"


def test_parse_fenced_json() -> None:
    text = (
        "Here you go:\n```json\n"
        '{"summary": "Meter shows zero", "board_visible": false, '
        '"meter_reading": "0.00 V"}\n```'
    )
    obs = parse_observation_text(text)
    assert obs.parse_status == "structured"
    assert obs.meter_reading == "0.00 V"
    assert obs.board_visible is False


def test_free_text_fallback() -> None:
    obs = parse_observation_text("I see a green PCB vaguely.")
    assert obs.parse_status == "free_text_fallback"
    assert "green PCB" in obs.summary
    assert obs.uncertainties


def test_empty_output() -> None:
    obs = parse_observation_text("   ")
    assert obs.parse_status == "empty"
