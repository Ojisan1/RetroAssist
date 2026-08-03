"""Capture types, encoding helpers, and shared capture utilities."""

from __future__ import annotations

import time
from abc import abstractmethod
from dataclasses import dataclass, field

import cv2
import numpy as np

from retroassist.interfaces import CaptureSource


class CaptureError(Exception):
    """Raised when a camera cannot be opened or read."""


@dataclass(frozen=True)
class CameraDeviceInfo:
    """A discovered capture device."""

    index: int
    name: str
    backend: str = ""


@dataclass
class Frame:
    """A single captured workbench frame (OpenCV BGR array)."""

    image: np.ndarray
    source_id: str
    role: str = "overview"
    timestamp: float = field(default_factory=time.time)
    backend: str = ""

    @property
    def width(self) -> int:
        return int(self.image.shape[1]) if self.image.ndim >= 2 else 0

    @property
    def height(self) -> int:
        return int(self.image.shape[0]) if self.image.ndim >= 2 else 0

    def copy(self) -> Frame:
        return Frame(
            image=self.image.copy(),
            source_id=self.source_id,
            role=self.role,
            timestamp=self.timestamp,
            backend=self.backend,
        )


@dataclass(frozen=True)
class EncodedFrame:
    """Frame encoded for VLM transport (JPEG bytes by default)."""

    source_id: str
    role: str
    timestamp: float
    mime_type: str
    data: bytes
    width: int
    height: int


def encode_frame_jpeg(frame: Frame, *, quality: int = 85) -> EncodedFrame:
    """Encode a BGR frame as JPEG bytes suitable for later VLM requests."""
    quality = max(1, min(100, int(quality)))
    ok, buf = cv2.imencode(".jpg", frame.image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise CaptureError(f"Failed to JPEG-encode frame from source {frame.source_id!r}")
    return EncodedFrame(
        source_id=frame.source_id,
        role=frame.role,
        timestamp=frame.timestamp,
        mime_type="image/jpeg",
        data=buf.tobytes(),
        width=frame.width,
        height=frame.height,
    )


def encode_frames_jpeg(frames: list[Frame], *, quality: int = 85) -> list[EncodedFrame]:
    return [encode_frame_jpeg(frame, quality=quality) for frame in frames]


def frame_change_score(previous: np.ndarray, current: np.ndarray) -> float:
    """Return a 0..1 change score between two BGR/gray frames (mean abs diff)."""
    if previous.shape != current.shape:
        return 1.0
    prev = previous
    curr = current
    if prev.ndim == 3:
        prev = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
        curr = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
    prev = cv2.resize(prev, (64, 64), interpolation=cv2.INTER_AREA)
    curr = cv2.resize(curr, (64, 64), interpolation=cv2.INTER_AREA)
    diff = cv2.absdiff(prev, curr)
    return float(np.mean(diff) / 255.0)


class BaseCaptureSource(CaptureSource):
    """Typed CaptureSource that returns ``Frame`` instances."""

    @abstractmethod
    def open(self) -> None:
        """Open the capture device."""

    @abstractmethod
    def close(self) -> None:
        """Release the capture device."""

    @abstractmethod
    def read(self) -> Frame | None:
        """Return the latest frame, or None if unavailable."""

    @abstractmethod
    def is_open(self) -> bool:
        """Whether the source is currently open."""
