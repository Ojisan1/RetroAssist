"""Unit tests for hybrid sampler timing and change detection."""

from __future__ import annotations

import numpy as np

from retroassist.capture.base import Frame, frame_change_score
from retroassist.capture.multi_camera import MultiCameraManager
from retroassist.capture.opencv_source import FixtureCaptureSource
from retroassist.capture.sampler import HybridSampler


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def _solid(bgr: tuple[int, int, int], size: int = 32) -> np.ndarray:
    image = np.zeros((size, size, 3), dtype=np.uint8)
    image[:] = bgr
    return image


def test_frame_change_score_identical_is_low() -> None:
    image = _solid((10, 20, 30))
    assert frame_change_score(image, image.copy()) < 0.01


def test_frame_change_score_different_is_high() -> None:
    a = _solid((0, 0, 0))
    b = _solid((255, 255, 255))
    assert frame_change_score(a, b) > 0.5


def test_continuous_rate_gates_samples() -> None:
    source = FixtureCaptureSource.__new__(FixtureCaptureSource)
    source.paths = []
    source.source_id = "fixture"
    source.role = "overview"
    source._images = [_solid((1, 2, 3))]
    source._index = 0
    source._opened = True

    manager = MultiCameraManager([source])
    clock = _Clock()
    sampler = HybridSampler(
        manager,
        continuous_fps=1.0,  # every 1.0s
        active_fps=5.0,
        change_detection=False,
        mode="continuous",
        time_fn=clock,
    )

    first = sampler.poll()
    assert first is not None and len(first) == 1

    clock.advance(0.4)
    assert sampler.poll() is None

    clock.advance(0.7)
    second = sampler.poll()
    assert second is not None


def test_active_mode_uses_higher_fps() -> None:
    source = FixtureCaptureSource.__new__(FixtureCaptureSource)
    source.paths = []
    source.source_id = "fixture"
    source.role = "overview"
    source._images = [_solid((9, 9, 9))]
    source._index = 0
    source._opened = True

    manager = MultiCameraManager([source])
    clock = _Clock()
    sampler = HybridSampler(
        manager,
        continuous_fps=0.5,  # 2s
        active_fps=2.0,  # 0.5s
        change_detection=False,
        mode="active",
        time_fn=clock,
    )
    assert sampler.poll() is not None
    clock.advance(0.4)
    assert sampler.poll() is None
    clock.advance(0.2)
    assert sampler.poll() is not None


def test_change_detection_triggers_early_sample() -> None:
    source = FixtureCaptureSource.__new__(FixtureCaptureSource)
    source.paths = []
    source.source_id = "fixture"
    source.role = "overview"
    source._images = [_solid((0, 0, 0))]
    source._index = 0
    source._opened = True

    manager = MultiCameraManager([source])
    clock = _Clock()
    sampler = HybridSampler(
        manager,
        continuous_fps=0.2,  # 5s interval
        change_detection=True,
        change_threshold=0.05,
        time_fn=clock,
    )
    assert sampler.poll() is not None

    clock.advance(0.1)
    # Same image — not due, no change
    assert sampler.poll() is None

    source._images = [_solid((255, 255, 255))]
    early = sampler.poll()
    assert early is not None


def test_look_now_encodes_jpeg() -> None:
    source = FixtureCaptureSource.__new__(FixtureCaptureSource)
    source.paths = []
    source.source_id = "fixture"
    source.role = "overview"
    source._images = [_solid((40, 80, 120), size=64)]
    source._index = 0
    source._opened = True

    manager = MultiCameraManager([source])
    sampler = HybridSampler(manager, change_detection=False)
    encoded = sampler.look_now()
    assert len(encoded) == 1
    assert encoded[0].mime_type == "image/jpeg"
    assert encoded[0].data[:2] == b"\xff\xd8"
    assert encoded[0].width == 64
    assert sampler.buffer["fixture"].source_id == "fixture"


def test_buffer_tracks_roles() -> None:
    overview = Frame(image=_solid((1, 1, 1)), source_id="ov", role="overview")
    close = Frame(image=_solid((2, 2, 2)), source_id="cu", role="close_up")

    class _Static:
        role = "overview"
        def is_open(self) -> bool:
            return True

        def open(self) -> None:
            return None

        def close(self) -> None:
            return None

        def read(self) -> Frame | None:
            return overview.copy()

    class _Static2(_Static):
        role = "close_up"

        def read(self) -> Frame | None:
            return close.copy()

    manager = MultiCameraManager([_Static(), _Static2()])  # type: ignore[list-item]
    sampler = HybridSampler(manager, change_detection=False, continuous_fps=10)
    frames = sampler.poll()
    assert frames is not None
    assert set(sampler.buffer) == {"ov", "cu"}
