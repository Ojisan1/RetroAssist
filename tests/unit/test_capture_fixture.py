"""Fixture / zero-camera capture path tests."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from retroassist.capture.base import CaptureError, encode_frame_jpeg
from retroassist.capture.multi_camera import MultiCameraManager
from retroassist.capture.opencv_source import FixtureCaptureSource, resolve_device_index
from retroassist.capture.sampler import HybridSampler
from retroassist.config import load_config

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "images" / "empty_bench" / "sample.png"
)


def test_fixture_source_loads_png() -> None:
    assert FIXTURE.is_file(), f"missing fixture image: {FIXTURE}"
    source = FixtureCaptureSource(FIXTURE, source_id="empty", role="overview")
    source.open()
    frame = source.read()
    assert frame is not None
    assert frame.height > 0 and frame.width > 0
    assert frame.backend == "fixture"
    source.close()
    assert source.read() is None


def test_fixture_manager_look_now() -> None:
    manager = MultiCameraManager.fixture_mode(FIXTURE)
    manager.open()
    sampler = HybridSampler(manager)
    encoded = sampler.look_now()
    assert len(encoded) == 1
    assert encoded[0].data
    manager.close()


def test_zero_camera_mode_from_config(tmp_path: Path) -> None:
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "platform")
    manager = MultiCameraManager.from_config(cfg)
    assert manager.zero_camera
    manager.open()
    assert manager.read_all() == []
    sampler = HybridSampler.from_config(cfg, manager)
    with pytest.raises(RuntimeError, match="zero-camera"):
        sampler.look_now()


def test_inject_in_memory_image() -> None:
    source = FixtureCaptureSource(FIXTURE)
    source.open()
    image = np.zeros((16, 24, 3), dtype=np.uint8)
    image[:] = (5, 15, 25)
    source.inject(image)
    frame = source.read()
    assert frame is not None
    assert frame.width == 24 and frame.height == 16
    encoded = encode_frame_jpeg(frame, quality=70)
    assert encoded.mime_type == "image/jpeg"


def test_resolve_device_numeric_string() -> None:
    assert resolve_device_index("3", devices=[]) == 3
    assert resolve_device_index(2, devices=[]) == 2


def test_resolve_device_name_match() -> None:
    from retroassist.capture.base import CameraDeviceInfo

    devices = [
        CameraDeviceInfo(0, "USB Camera"),
        CameraDeviceInfo(1, "OBS Virtual Camera"),
    ]
    assert resolve_device_index("OBS Virtual Camera", devices=devices) == 1
    assert resolve_device_index("obs virtual", devices=devices) == 1


def test_resolve_device_ambiguous() -> None:
    from retroassist.capture.base import CameraDeviceInfo

    devices = [
        CameraDeviceInfo(0, "Cam A"),
        CameraDeviceInfo(1, "Cam B"),
    ]
    with pytest.raises(CaptureError, match="Ambiguous"):
        resolve_device_index("Cam", devices=devices)


def test_multi_role_fixture_paths(tmp_path: Path) -> None:
    overview = tmp_path / "overview.png"
    closeup = tmp_path / "close.png"
    cv2.imwrite(str(overview), np.full((8, 8, 3), 10, dtype=np.uint8))
    cv2.imwrite(str(closeup), np.full((8, 8, 3), 200, dtype=np.uint8))

    manager = MultiCameraManager(
        [
            FixtureCaptureSource(overview, source_id="ov", role="overview"),
            FixtureCaptureSource(closeup, source_id="cu", role="close_up"),
        ]
    )
    manager.open()
    frames = manager.read_all()
    assert {f.role for f in frames} == {"overview", "close_up"}
    by_role = manager.read_by_role("close_up")
    assert by_role is not None
    assert by_role.source_id == "cu"
