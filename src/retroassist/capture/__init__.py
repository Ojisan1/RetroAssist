"""Workbench capture: OpenCV sources, multi-cam, hybrid sampling."""

from retroassist.capture.base import (
    BaseCaptureSource,
    CameraDeviceInfo,
    CaptureError,
    EncodedFrame,
    Frame,
    encode_frame_jpeg,
    encode_frames_jpeg,
    frame_change_score,
)
from retroassist.capture.multi_camera import MultiCameraManager
from retroassist.capture.opencv_source import (
    FixtureCaptureSource,
    OpenCVCaptureSource,
    enumerate_devices,
    preferred_backend,
    resolve_device_index,
)
from retroassist.capture.sampler import HybridSampler

__all__ = [
    "BaseCaptureSource",
    "CameraDeviceInfo",
    "CaptureError",
    "EncodedFrame",
    "FixtureCaptureSource",
    "Frame",
    "HybridSampler",
    "MultiCameraManager",
    "OpenCVCaptureSource",
    "encode_frame_jpeg",
    "encode_frames_jpeg",
    "enumerate_devices",
    "frame_change_score",
    "preferred_backend",
    "resolve_device_index",
]
