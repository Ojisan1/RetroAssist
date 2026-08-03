"""Hybrid visual sampler: continuous / active rates, change detection, look-now."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Literal

import numpy as np

from retroassist.capture.base import EncodedFrame, Frame, encode_frames_jpeg, frame_change_score
from retroassist.capture.multi_camera import MultiCameraManager
from retroassist.config import AppConfig

SampleMode = Literal["continuous", "active"]


class HybridSampler:
    """Decide when to emit frames from a ``MultiCameraManager``.

    - continuous: low fps background observation (default ~0.4 fps)
    - active: higher fps while probing (default ~1 fps)
    - change detection can trigger an early sample within the interval
    - ``look_now()`` always captures + JPEG-encodes the current frames
    """

    def __init__(
        self,
        manager: MultiCameraManager,
        *,
        continuous_fps: float = 0.4,
        active_fps: float = 1.0,
        change_detection: bool = True,
        change_threshold: float = 0.05,
        on_demand_enabled: bool = True,
        jpeg_quality: int = 85,
        mode: SampleMode = "continuous",
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self.manager = manager
        self.continuous_fps = max(0.0, float(continuous_fps))
        self.active_fps = max(0.0, float(active_fps))
        self.change_detection = bool(change_detection)
        self.change_threshold = float(change_threshold)
        self.on_demand_enabled = bool(on_demand_enabled)
        self.jpeg_quality = int(jpeg_quality)
        self.mode: SampleMode = mode
        self._time = time_fn or time.monotonic
        self._last_sample_at: float | None = None
        self._last_images: dict[str, np.ndarray] = {}
        self._buffer: dict[str, Frame] = {}

    @classmethod
    def from_config(cls, config: AppConfig, manager: MultiCameraManager) -> HybridSampler:
        sampling = config.raw.get("sampling") or {}
        return cls(
            manager,
            continuous_fps=float(sampling.get("continuous_fps", 0.4)),
            active_fps=float(sampling.get("active_fps", 1.0)),
            change_detection=bool(sampling.get("change_detection", True)),
            change_threshold=float(sampling.get("change_threshold", 0.05)),
            on_demand_enabled=bool(sampling.get("on_demand_enabled", True)),
            jpeg_quality=int(sampling.get("jpeg_quality", 85)),
        )

    def set_mode(self, mode: SampleMode) -> None:
        if mode not in ("continuous", "active"):
            raise ValueError(f"mode must be 'continuous' or 'active', got {mode!r}")
        self.mode = mode

    @property
    def target_fps(self) -> float:
        return self.active_fps if self.mode == "active" else self.continuous_fps

    @property
    def buffer(self) -> dict[str, Frame]:
        return {key: frame.copy() for key, frame in self._buffer.items()}

    def _interval(self) -> float:
        fps = self.target_fps
        if fps <= 0:
            return float("inf")
        return 1.0 / fps

    def poll(self) -> list[Frame] | None:
        """Read and return frames if the sampling policy says it is time.

        Returns None when no sample should be emitted yet (or no frames available).
        """
        now = self._time()
        due = self._last_sample_at is None or (now - self._last_sample_at) >= self._interval()

        frames = self.manager.read_all()
        if not frames:
            return None

        changed = False
        if self.change_detection:
            changed = self._detect_change(frames)

        if not due and not changed:
            # Keep buffer fresh even when not emitting.
            self._update_buffer(frames)
            return None

        self._last_sample_at = now
        self._update_buffer(frames)
        self._remember_images(frames)
        return [frame.copy() for frame in frames]

    def look_now(self) -> list[EncodedFrame]:
        """On-demand capture: read current frames and JPEG-encode for VLM use."""
        if not self.on_demand_enabled:
            raise RuntimeError(
                "On-demand look_now is disabled in config (sampling.on_demand_enabled)"
            )
        frames = self.manager.read_all()
        if not frames and self.manager.zero_camera:
            raise RuntimeError(
                "look_now() called in zero-camera mode with no fixture sources; "
                "add cameras.sources or use MultiCameraManager.fixture_mode(...)."
            )
        self._last_sample_at = self._time()
        self._update_buffer(frames)
        self._remember_images(frames)
        return encode_frames_jpeg(frames, quality=self.jpeg_quality)

    def encode_buffer(self) -> list[EncodedFrame]:
        """JPEG-encode the last buffered frames without capturing anew."""
        frames = list(self._buffer.values())
        return encode_frames_jpeg(frames, quality=self.jpeg_quality)

    def _update_buffer(self, frames: list[Frame]) -> None:
        for frame in frames:
            self._buffer[frame.source_id] = frame.copy()

    def _remember_images(self, frames: list[Frame]) -> None:
        for frame in frames:
            self._last_images[frame.source_id] = frame.image.copy()

    def _detect_change(self, frames: list[Frame]) -> bool:
        if not self._last_images:
            return False
        for frame in frames:
            previous = self._last_images.get(frame.source_id)
            if previous is None:
                return True
            score = frame_change_score(previous, frame.image)
            if score >= self.change_threshold:
                return True
        return False
