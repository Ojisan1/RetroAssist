"""Mock / recorded agent LLM responses for CI keyframe cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MockAgentLLM:
    """Returns canned suggestion JSON for a case id (CI-safe)."""

    def __init__(self, store_root: Path | None = None, *, case_id: str = "default") -> None:
        if store_root is None:
            store_root = (
                Path(__file__).resolve().parents[3]
                / "tests"
                / "fixtures"
                / "agent"
                / "responses"
            )
        self.store_root = store_root
        self.case_id = case_id
        self.calls: list[dict[str, Any]] = []

    def set_case(self, case_id: str) -> None:
        self.case_id = case_id

    def load(self, case_id: str | None = None) -> dict[str, Any]:
        cid = case_id or self.case_id
        path = self.store_root / f"{cid}.json"
        if not path.is_file():
            raise FileNotFoundError(f"No mock agent response for {cid!r} at {path}")
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Mock agent response must be an object: {path}")
        return data

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "mock-agent",
        **_: Any,
    ) -> Any:
        from retroassist.llm.client import ChatResult

        payload = self.load(self.case_id)
        self.calls.append({"model": model, "messages": messages, "case_id": self.case_id})
        if "content" in payload and isinstance(payload["content"], str):
            content = payload["content"]
        else:
            suggestion = payload.get("suggestion") or payload
            content = json.dumps(suggestion)
        return ChatResult(content=content, model=model, raw={"mock": True, "case_id": self.case_id})

    async def aclose(self) -> None:
        return None
