"""OpenCV capture source (USB webcams, capture cards, OBS Virtual Camera)."""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

from retroassist.capture.base import (
    BaseCaptureSource,
    CameraDeviceInfo,
    CaptureError,
    Frame,
)


def preferred_backend() -> int:
    """Prefer DirectShow on Windows; default backend elsewhere."""
    if os.name == "nt" and hasattr(cv2, "CAP_DSHOW"):
        return int(cv2.CAP_DSHOW)
    return int(cv2.CAP_ANY)


def enumerate_devices(*, max_index: int = 10, probe_frame: bool = True) -> list[CameraDeviceInfo]:
    """Probe camera indices and attach friendly names when available.

    OBS Virtual Camera appears as a normal device (index and/or name).
    Friendly names are best-effort via ffmpeg DirectShow listing on Windows.
    """
    names_by_index = _friendly_names_by_index()
    backend = preferred_backend()
    backend_name = _backend_label(backend)
    found: list[CameraDeviceInfo] = []

    for index in range(max(0, int(max_index))):
        cap = cv2.VideoCapture(index, backend)
        try:
            if not cap.isOpened():
                continue
            if probe_frame:
                # Short read; do not block forever on misbehaving drivers.
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                ok, _ = cap.read()
                if not ok:
                    pass
            name = names_by_index.get(index) or f"Camera {index}"
            found.append(CameraDeviceInfo(index=index, name=name, backend=backend_name))
        finally:
            cap.release()
    return found


def resolve_device_index(
    device: int | str,
    *,
    devices: list[CameraDeviceInfo] | None = None,
    max_index: int = 10,
) -> int:
    """Resolve a configured device index or name to an OpenCV index."""
    if isinstance(device, int):
        return device
    text = str(device).strip()
    if re.fullmatch(r"\d+", text):
        return int(text)

    catalog = devices if devices is not None else enumerate_devices(max_index=max_index)
    needle = text.casefold()
    exact = [d for d in catalog if d.name.casefold() == needle]
    if exact:
        return exact[0].index
    partial = [d for d in catalog if needle in d.name.casefold()]
    if len(partial) == 1:
        return partial[0].index
    if len(partial) > 1:
        options = ", ".join(f"{d.index}:{d.name}" for d in partial)
        raise CaptureError(
            f"Ambiguous camera name {device!r}; matches: {options}. Use a numeric index."
        )
    listed = ", ".join(f"{d.index}:{d.name}" for d in catalog) or "(none found)"
    raise CaptureError(
        f"No camera matched {device!r}. Enumerated devices: {listed}. "
        "Tip: set cameras.sources[].device to a numeric index from `retroassist doctor`."
    )


def _backend_label(backend: int) -> str:
    try:
        return str(cv2.videoio_registry.getBackendName(backend))
    except Exception:  # noqa: BLE001 - backend naming is best-effort
        if backend == getattr(cv2, "CAP_DSHOW", None):
            return "DSHOW"
        return "ANY"


def _friendly_names_by_index() -> dict[int, str]:
    """Best-effort map of index → friendly name (Windows ffmpeg dshow)."""
    if os.name != "nt":
        return {}
    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        return {}
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}

    # ffmpeg prints device list to stderr
    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    names: list[str] = []
    in_video = False
    for line in text.splitlines():
        lower = line.lower()
        if "directshow video devices" in lower:
            in_video = True
            continue
        if in_video and "directshow audio devices" in lower:
            break
        if not in_video:
            continue
        match = re.search(r'"([^"]+)"', line)
        if match:
            names.append(match.group(1))
    return {index: name for index, name in enumerate(names)}


def _find_ffmpeg() -> str | None:
    from shutil import which

    return which("ffmpeg")


class OpenCVCaptureSource(BaseCaptureSource):
    """Capture frames from an OpenCV device index or friendly name."""

    def __init__(
        self,
        device: int | str,
        *,
        source_id: str = "camera",
        role: str = "overview",
        open_timeout_seconds: float = 5.0,
        reconnect_interval_seconds: float = 2.0,
        max_reconnect_attempts: int = 3,
        enumerate_max_index: int = 10,
        backend: int | None = None,
    ) -> None:
        self.device = device
        self.source_id = source_id
        self.role = role
        self.open_timeout_seconds = open_timeout_seconds
        self.reconnect_interval_seconds = reconnect_interval_seconds
        self.max_reconnect_attempts = max_reconnect_attempts
        self.enumerate_max_index = enumerate_max_index
        self.backend = preferred_backend() if backend is None else backend
        self._cap: cv2.VideoCapture | None = None
        self._resolved_index: int | None = None

    def open(self) -> None:
        if self.is_open():
            return
        index = resolve_device_index(
            self.device,
            max_index=self.enumerate_max_index,
        )
        self._resolved_index = index
        deadline = time.monotonic() + max(0.1, self.open_timeout_seconds)
        last_error = "unknown"
        while time.monotonic() < deadline:
            cap = cv2.VideoCapture(index, self.backend)
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    # Rewind is not available on live cams; keep device open.
                    self._cap = cap
                    return
                cap.release()
                last_error = "opened but failed to read a frame"
            else:
                cap.release()
                last_error = "VideoCapture failed to open"
            time.sleep(min(0.25, self.reconnect_interval_seconds))
        raise CaptureError(
            f"Timed out opening camera device={self.device!r} index={index}: {last_error}"
        )

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> Frame | None:
        if not self.is_open():
            return None
        assert self._cap is not None
        ok, image = self._cap.read()
        if not ok or image is None:
            if self._reconnect():
                assert self._cap is not None
                ok, image = self._cap.read()
                if not ok or image is None:
                    return None
            else:
                return None
        return Frame(
            image=image,
            source_id=self.source_id,
            role=self.role,
            timestamp=time.time(),
            backend=_backend_label(self.backend),
        )

    def _reconnect(self) -> bool:
        self.close()
        attempts = max(1, int(self.max_reconnect_attempts))
        for _ in range(attempts):
            try:
                self.open()
                return self.is_open()
            except CaptureError:
                time.sleep(self.reconnect_interval_seconds)
        return False


class FixtureCaptureSource(BaseCaptureSource):
    """Zero-camera / CI source that serves one or more images from disk."""

    def __init__(
        self,
        paths: list[Path] | Path,
        *,
        source_id: str = "fixture",
        role: str = "overview",
    ) -> None:
        if isinstance(paths, Path):
            path_list = [paths]
        else:
            path_list = list(paths)
        if not path_list:
            raise CaptureError("FixtureCaptureSource requires at least one image path")
        self.paths = path_list
        self.source_id = source_id
        self.role = role
        self._images: list[np.ndarray] = []
        self._index = 0
        self._opened = False

    def open(self) -> None:
        images: list[np.ndarray] = []
        for path in self.paths:
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                raise CaptureError(f"Could not load fixture image: {path}")
            images.append(image)
        self._images = images
        self._index = 0
        self._opened = True

    def close(self) -> None:
        self._opened = False
        self._images = []

    def is_open(self) -> bool:
        return self._opened and bool(self._images)

    def read(self) -> Frame | None:
        if not self.is_open():
            return None
        image = self._images[self._index % len(self._images)]
        self._index += 1
        return Frame(
            image=image.copy(),
            source_id=self.source_id,
            role=self.role,
            timestamp=time.time(),
            backend="fixture",
        )

    def inject(self, image: np.ndarray) -> None:
        """Replace the fixture sequence with an in-memory BGR image (tests)."""
        if image is None or not isinstance(image, np.ndarray):
            raise CaptureError("inject() requires a numpy BGR image")
        self._images = [image.copy()]
        self._index = 0
        self._opened = True
