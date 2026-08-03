"""Multi-camera manager with overview / close-up roles and zero-camera mode."""

from __future__ import annotations

from pathlib import Path

from retroassist.capture.base import BaseCaptureSource, CaptureError, Frame
from retroassist.capture.opencv_source import FixtureCaptureSource, OpenCVCaptureSource
from retroassist.config import AppConfig, CameraSourceConfig


class MultiCameraManager:
    """Owns one or more capture sources and reads the latest frame set."""

    def __init__(self, sources: list[BaseCaptureSource] | None = None) -> None:
        self._sources: list[BaseCaptureSource] = list(sources or [])
        self._opened = False

    @classmethod
    def from_config(cls, config: AppConfig) -> MultiCameraManager:
        """Build sources from config. Empty sources ⇒ zero-camera mode."""
        camera_cfg = config.raw.get("cameras") or {}
        open_timeout = float(camera_cfg.get("open_timeout_seconds", 5.0))
        reconnect_interval = float(camera_cfg.get("reconnect_interval_seconds", 2.0))
        max_reconnect = int(camera_cfg.get("max_reconnect_attempts", 3))
        max_index = int(camera_cfg.get("enumerate_max_index", 10))

        configured = config.camera_sources()
        sources: list[BaseCaptureSource] = []
        for item in configured:
            sources.append(
                OpenCVCaptureSource(
                    item.device,
                    source_id=item.id,
                    role=item.role,
                    open_timeout_seconds=open_timeout,
                    reconnect_interval_seconds=reconnect_interval,
                    max_reconnect_attempts=max_reconnect,
                    enumerate_max_index=max_index,
                )
            )
        return cls(sources)

    @classmethod
    def fixture_mode(
        cls,
        paths: list[Path] | Path,
        *,
        source_id: str = "fixture",
        role: str = "overview",
    ) -> MultiCameraManager:
        """Headless manager that serves fixture image(s) only."""
        return cls([FixtureCaptureSource(paths, source_id=source_id, role=role)])

    @property
    def sources(self) -> list[BaseCaptureSource]:
        return list(self._sources)

    @property
    def zero_camera(self) -> bool:
        return len(self._sources) == 0

    def add_source(self, source: BaseCaptureSource) -> None:
        self._sources.append(source)

    def open(self) -> None:
        errors: list[str] = []
        for source in self._sources:
            try:
                source.open()
            except CaptureError as exc:
                errors.append(str(exc))
        if errors and not any(s.is_open() for s in self._sources):
            raise CaptureError("Failed to open any capture source: " + "; ".join(errors))
        self._opened = True

    def close(self) -> None:
        for source in self._sources:
            source.close()
        self._opened = False

    def is_open(self) -> bool:
        if self.zero_camera:
            return self._opened
        return any(source.is_open() for source in self._sources)

    def read_all(self) -> list[Frame]:
        """Read one frame from each open source (skips failures)."""
        frames: list[Frame] = []
        for source in self._sources:
            if not source.is_open():
                continue
            frame = source.read()
            if frame is not None:
                frames.append(frame)
        return frames

    def read_by_role(self, role: str) -> Frame | None:
        for source in self._sources:
            if getattr(source, "role", None) == role and source.is_open():
                frame = source.read()
                if frame is not None:
                    return frame
        return None

    def roles(self) -> list[str]:
        return [getattr(s, "role", "overview") for s in self._sources]


def sources_from_camera_configs(
    items: list[CameraSourceConfig],
    **kwargs: object,
) -> list[OpenCVCaptureSource]:
    """Helper used by tests/tools to build OpenCV sources from dataclasses."""
    return [
        OpenCVCaptureSource(item.device, source_id=item.id, role=item.role, **kwargs)  # type: ignore[arg-type]
        for item in items
    ]
