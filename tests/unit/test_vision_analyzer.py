"""Vision analyzer tests using fixture images + mocked VLM responses."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from retroassist.capture.base import Frame
from retroassist.config import load_config
from retroassist.vision.analyzer import WorkbenchVisionAnalyzer, frames_from_image_paths
from retroassist.vision.mock_store import MockLLMClient, MockVLMStore

IMAGES = Path(__file__).resolve().parents[1] / "fixtures" / "images"
RESPONSES = Path(__file__).resolve().parents[1] / "fixtures" / "vision" / "responses"


def _analyzer(case_id: str) -> tuple[WorkbenchVisionAnalyzer, MockLLMClient]:
    store = MockVLMStore(RESPONSES)
    client = MockLLMClient(store, case_id=case_id)
    analyzer = WorkbenchVisionAnalyzer(
        client,
        model="mock-vlm",
        latency_target_seconds=6.0,
        latency_log_enabled=False,
    )
    return analyzer, client


@pytest.mark.parametrize(
    ("case_id", "expect_board"),
    [
        ("empty_bench", False),
        ("power_supply", True),
        ("logic_board", True),
        ("meter_readings", False),
    ],
)
@pytest.mark.asyncio
async def test_mocked_keyframe_analysis(case_id: str, expect_board: bool) -> None:
    path = IMAGES / case_id / "sample.png"
    assert path.is_file(), path
    frames = frames_from_image_paths([str(path)])
    assert frames
    analyzer, client = _analyzer(case_id)
    obs = await analyzer.analyze_frames(frames)
    assert obs.parse_status == "structured"
    assert obs.board_visible is expect_board
    assert obs.latency_ms is not None
    assert obs.latency_within_target is True
    assert analyzer.last_observation is not None
    assert client.calls and client.calls[0]["image_count"] == 1
    if case_id == "meter_readings":
        assert obs.meter_reading and "0.00" in obs.meter_reading
    if case_id == "empty_bench":
        assert "board" in obs.summary.lower() or obs.board_visible is False


@pytest.mark.asyncio
async def test_multi_image_overview_and_close_up() -> None:
    overview = frames_from_image_paths(
        [str(IMAGES / "logic_board" / "sample.png")],
        role="overview",
    )
    close = frames_from_image_paths(
        [str(IMAGES / "meter_readings" / "sample.png")],
        role="close_up",
    )
    frames = [overview[0], close[0]]
    # Force roles explicitly
    frames[0].role = "overview"
    frames[1].role = "close_up"
    analyzer, client = _analyzer("logic_board")
    obs = await analyzer.analyze_frames(frames, prompt="What should I notice first?")
    assert obs.roles == ["overview", "close_up"]
    assert client.calls[0]["image_count"] == 2
    prompt = client.calls[0]["prompt"].lower()
    assert "close-up" in prompt or "close_up" in prompt


@pytest.mark.asyncio
async def test_cache_and_supersede() -> None:
    frames = frames_from_image_paths([str(IMAGES / "power_supply" / "sample.png")])
    analyzer, _client = _analyzer("power_supply")

    first = await analyzer.analyze_frames(frames)
    assert analyzer.last_observation is first or analyzer.last_observation is not None
    assert analyzer.last_observation is not None
    assert analyzer.last_observation.analysis_id == first.analysis_id

    second = await analyzer.analyze_frames(frames)
    assert second.analysis_id > first.analysis_id
    assert analyzer.last_observation is not None
    assert analyzer.last_observation.analysis_id == second.analysis_id
    assert second.superseded is False


@pytest.mark.asyncio
async def test_supersede_marks_stale_in_flight_result() -> None:
    """If a newer analyze starts while one awaits, the older result is marked superseded."""

    class SlowThenMock(MockLLMClient):
        def __init__(self) -> None:
            super().__init__(MockVLMStore(RESPONSES), case_id="empty_bench")
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def chat_with_images(self, **kwargs):  # type: ignore[no-untyped-def]
            self.started.set()
            await self.release.wait()
            return await super().chat_with_images(**kwargs)

    client = SlowThenMock()
    analyzer = WorkbenchVisionAnalyzer(client, model="mock-vlm", latency_log_enabled=False)
    frame = frames_from_image_paths([str(IMAGES / "empty_bench" / "sample.png")])[0]

    task1 = asyncio.create_task(analyzer.analyze_frames([frame]))
    await client.started.wait()
    # Second call supersedes; use a fast client path by swapping client mid-flight
    fast = MockLLMClient(MockVLMStore(RESPONSES), case_id="meter_readings")
    analyzer.client = fast
    second = await analyzer.analyze_frames([frame])
    client.release.set()
    first = await task1

    assert first.superseded is True
    assert second.superseded is False
    assert analyzer.last_observation is not None
    assert analyzer.last_observation.analysis_id == second.analysis_id


@pytest.mark.asyncio
async def test_from_config_uses_vision_model(tmp_path: Path) -> None:
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "platform")
    client = MockLLMClient(MockVLMStore(RESPONSES), case_id="empty_bench")
    analyzer = WorkbenchVisionAnalyzer.from_config(cfg, client)
    assert analyzer.model == cfg.resolved_models()["vision"]
    frame = Frame(
        image=frames_from_image_paths([str(IMAGES / "empty_bench" / "sample.png")])[0].image,
        source_id="t",
        role="overview",
    )
    obs = await analyzer.analyze([frame])
    assert obs["parse_status"] == "structured"
    assert "latency_ms" in obs


@pytest.mark.asyncio
async def test_optional_live_vlm_skips_without_ollama() -> None:
    """Live path is optional; skip cleanly when Ollama is unreachable."""
    from retroassist.llm.client import LLMClient, LLMUnavailableError

    client = LLMClient(base_url="http://127.0.0.1:9/v1", timeout_seconds=0.5)
    analyzer = WorkbenchVisionAnalyzer(client, model="does-not-matter", latency_log_enabled=False)
    frames = frames_from_image_paths([str(IMAGES / "empty_bench" / "sample.png")])
    try:
        await analyzer.analyze_frames(frames)
    except LLMUnavailableError:
        pytest.skip("Ollama not available for live vision latency check")
    finally:
        await client.aclose()
