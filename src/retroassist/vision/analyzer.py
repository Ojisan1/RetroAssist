"""Multimodal vision analyzer: frames → structured observations."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any, Protocol

import cv2
import numpy as np

from retroassist.capture.base import EncodedFrame, Frame, encode_frame_jpeg
from retroassist.config import AppConfig
from retroassist.interfaces import VisionAnalyzer
from retroassist.vision.prompts import SYSTEM_PROMPT, build_user_prompt
from retroassist.vision.schema import VisionObservation, parse_observation_text

logger = logging.getLogger(__name__)


class SupportsChatWithImages(Protocol):
    async def chat_with_images(
        self,
        *,
        model: str,
        prompt: str,
        images: Sequence[bytes],
        system: str | None = None,
        mime_type: str = "image/jpeg",
    ) -> Any: ...


class WorkbenchVisionAnalyzer(VisionAnalyzer):
    """Analyze workbench frames via an OpenAI-compatible vision model."""

    def __init__(
        self,
        client: SupportsChatWithImages,
        *,
        model: str,
        jpeg_quality: int = 85,
        max_images: int = 4,
        latency_target_seconds: float = 6.0,
        latency_log_enabled: bool = True,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self.client = client
        self.model = model
        self.jpeg_quality = jpeg_quality
        self.max_images = max(1, int(max_images))
        self.latency_target_seconds = float(latency_target_seconds)
        self.latency_log_enabled = bool(latency_log_enabled)
        self.system_prompt = system_prompt
        self._analysis_seq = 0
        self._active_analysis_id: int | None = None
        self._cache: VisionObservation | None = None

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        client: SupportsChatWithImages,
    ) -> WorkbenchVisionAnalyzer:
        vision_cfg = config.raw.get("vision") or {}
        models = config.resolved_models()
        latency = config.raw.get("latency") or {}
        sampling = config.raw.get("sampling") or {}
        return cls(
            client,
            model=models["vision"],
            jpeg_quality=int(vision_cfg.get("jpeg_quality", sampling.get("jpeg_quality", 85))),
            max_images=int(vision_cfg.get("max_images", 4)),
            latency_target_seconds=float(latency.get("look_now_target_seconds", 6.0)),
            latency_log_enabled=bool(latency.get("log_enabled", True)),
        )

    @property
    def last_observation(self) -> VisionObservation | None:
        return self._cache

    def clear_cache(self) -> None:
        self._cache = None

    async def analyze(
        self,
        frames: Sequence[Any],
        *,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        observation = await self.analyze_frames(frames, prompt=prompt)
        return observation.to_dict()

    async def analyze_frames(
        self,
        frames: Sequence[Frame | EncodedFrame | np.ndarray | bytes],
        *,
        prompt: str | None = None,
    ) -> VisionObservation:
        """Analyze frames and return a typed observation (cached; supersedes in-flight)."""
        self._analysis_seq += 1
        analysis_id = self._analysis_seq
        self._active_analysis_id = analysis_id

        encoded, roles, source_ids = self._prepare_images(frames)
        if not encoded:
            observation = VisionObservation(
                summary="No frames provided for analysis.",
                board_visible=False,
                parse_status="empty",
                analysis_id=analysis_id,
                uncertainties=["No frames provided."],
            )
            return self._finalize(analysis_id, observation, latency_ms=0.0)

        user_prompt = build_user_prompt(extra_prompt=prompt, roles=roles)
        started = time.perf_counter()
        result = await self.client.chat_with_images(
            model=self.model,
            prompt=user_prompt,
            images=[item.data for item in encoded],
            system=self.system_prompt,
            mime_type=encoded[0].mime_type,
        )
        latency_ms = (time.perf_counter() - started) * 1000.0

        # Superseded if a newer analyze started while we awaited the VLM.
        if self._active_analysis_id != analysis_id:
            observation = parse_observation_text(result.content, model=result.model)
            observation.analysis_id = analysis_id
            observation.superseded = True
            observation.source_ids = source_ids
            observation.roles = roles
            observation.latency_ms = latency_ms
            observation.latency_target_seconds = self.latency_target_seconds
            observation.latency_within_target = latency_ms <= self.latency_target_seconds * 1000.0
            if self.latency_log_enabled:
                logger.info(
                    "vision.analyze superseded id=%s latency_ms=%.1f",
                    analysis_id,
                    latency_ms,
                )
            return observation

        observation = parse_observation_text(result.content, model=result.model)
        observation.source_ids = source_ids
        observation.roles = roles
        return self._finalize(analysis_id, observation, latency_ms=latency_ms)

    def _finalize(
        self,
        analysis_id: int,
        observation: VisionObservation,
        *,
        latency_ms: float,
    ) -> VisionObservation:
        observation.analysis_id = analysis_id
        observation.superseded = False
        observation.latency_ms = latency_ms
        observation.latency_target_seconds = self.latency_target_seconds
        within = latency_ms <= self.latency_target_seconds * 1000.0
        observation.latency_within_target = within
        if self.latency_log_enabled:
            level = logging.INFO if within else logging.WARNING
            logger.log(
                level,
                "vision.analyze id=%s latency_ms=%.1f target_s=%.1f within_target=%s parse=%s",
                analysis_id,
                latency_ms,
                self.latency_target_seconds,
                within,
                observation.parse_status,
            )
        self._cache = observation
        return observation

    def _prepare_images(
        self,
        frames: Sequence[Frame | EncodedFrame | np.ndarray | bytes],
    ) -> tuple[list[EncodedFrame], list[str], list[str]]:
        encoded: list[EncodedFrame] = []
        roles: list[str] = []
        source_ids: list[str] = []
        for idx, item in enumerate(frames):
            if len(encoded) >= self.max_images:
                break
            frame = self._coerce_encoded(item, index=idx)
            if frame is None:
                continue
            encoded.append(frame)
            roles.append(frame.role)
            source_ids.append(frame.source_id)
        # Prefer overview then close_up ordering when both present
        order = {"overview": 0, "close_up": 1, "other": 2}
        ranked = sorted(
            range(len(encoded)),
            key=lambda i: order.get(roles[i], 9),
        )
        encoded = [encoded[i] for i in ranked]
        roles = [roles[i] for i in ranked]
        source_ids = [source_ids[i] for i in ranked]
        return encoded, roles, source_ids

    def _coerce_encoded(
        self,
        item: Frame | EncodedFrame | np.ndarray | bytes,
        *,
        index: int,
    ) -> EncodedFrame | None:
        if isinstance(item, EncodedFrame):
            return item
        if isinstance(item, Frame):
            return encode_frame_jpeg(item, quality=self.jpeg_quality)
        if isinstance(item, (bytes, bytearray)):
            return EncodedFrame(
                source_id=f"bytes-{index}",
                role="overview",
                timestamp=time.time(),
                mime_type="image/jpeg",
                data=bytes(item),
                width=0,
                height=0,
            )
        if isinstance(item, np.ndarray):
            frame = Frame(image=item, source_id=f"array-{index}", role="overview")
            return encode_frame_jpeg(frame, quality=self.jpeg_quality)
        return None


def frames_from_image_paths(paths: Sequence[str], *, role: str = "overview") -> list[Frame]:
    """Load BGR frames from disk paths (fixture helper)."""
    frames: list[Frame] = []
    for idx, path in enumerate(paths):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            continue
        frames.append(
            Frame(
                image=image,
                source_id=f"file-{idx}",
                role=role if idx == 0 else "close_up",
            )
        )
    return frames
