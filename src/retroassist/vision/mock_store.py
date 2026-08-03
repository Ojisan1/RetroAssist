"""Recorded / mocked VLM responses for CI keyframe tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MockVLMStore:
    """Load canned vision-model responses keyed by case id."""

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            # tests/fixtures/vision/responses relative to repo when installed editable
            root = (
                Path(__file__).resolve().parents[3]
                / "tests"
                / "fixtures"
                / "vision"
                / "responses"
            )
        self.root = root

    def path_for(self, case_id: str) -> Path:
        return self.root / f"{case_id}.json"

    def has(self, case_id: str) -> bool:
        return self.path_for(case_id).is_file()

    def load(self, case_id: str) -> dict[str, Any]:
        path = self.path_for(case_id)
        if not path.is_file():
            raise FileNotFoundError(f"No mocked VLM response for case {case_id!r} at {path}")
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Mock response {path} must be a JSON object")
        return data

    def response_text(self, case_id: str) -> str:
        """Return the model content string for a case (JSON object serialized if needed)."""
        data = self.load(case_id)
        if "content" in data and isinstance(data["content"], str):
            return data["content"]
        if "observation" in data and isinstance(data["observation"], dict):
            return json.dumps(data["observation"])
        # Treat the file itself as the observation payload
        return json.dumps({k: v for k, v in data.items() if k not in {"case_id", "notes"}})

    def list_cases(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.stem for p in self.root.glob("*.json"))


class MockLLMClient:
    """Drop-in async client stub that returns canned chat_with_images content."""

    def __init__(self, store: MockVLMStore, *, case_id: str, model_name: str = "mock-vlm") -> None:
        self.store = store
        self.case_id = case_id
        self.model_name = model_name
        self.calls: list[dict[str, Any]] = []

    async def chat_with_images(
        self,
        *,
        model: str,
        prompt: str,
        images: list[bytes] | tuple[bytes, ...],
        system: str | None = None,
        mime_type: str = "image/jpeg",
    ) -> Any:
        from retroassist.llm.client import ChatResult

        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "system": system,
                "image_count": len(images),
                "mime_type": mime_type,
            }
        )
        content = self.store.response_text(self.case_id)
        return ChatResult(content=content, model=model or self.model_name, raw={"mock": True})

    async def aclose(self) -> None:
        return None
