"""Unit tests for OpenAI-compatible LLM client helpers."""

from __future__ import annotations

import json

import httpx
import pytest

from retroassist.llm.client import LLMClient, LLMUnavailableError


class _Handler(httpx.AsyncBaseTransport):
    def __init__(self, routes: dict[str, httpx.Response]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(f"{request.method} {request.url.path}")
        key = f"{request.method} {request.url.path}"
        if key in self.routes:
            return self.routes[key]
        return httpx.Response(404, json={"error": "missing"})


@pytest.mark.asyncio
async def test_health_check_and_list_models() -> None:
    transport = _Handler(
        {
            "GET /v1/models": httpx.Response(
                200,
                json={"data": [{"id": "qwen2.5:7b"}, {"id": "nomic-embed-text"}]},
            )
        }
    )
    async with LLMClient(base_url="http://test/v1", transport=transport) as client:
        names = await client.list_models()
    assert names == ["qwen2.5:7b", "nomic-embed-text"]


@pytest.mark.asyncio
async def test_health_check_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    transport = httpx.MockTransport(handler)
    client = LLMClient(base_url="http://127.0.0.1:9/v1", transport=transport)
    with pytest.raises(LLMUnavailableError, match="unreachable"):
        await client.health_check()
    await client.aclose()


@pytest.mark.asyncio
async def test_chat_completion() -> None:
    body = {
        "id": "chatcmpl-1",
        "model": "qwen2.5:7b",
        "choices": [{"message": {"role": "assistant", "content": "Check the fuse."}}],
    }
    transport = _Handler({"POST /v1/chat/completions": httpx.Response(200, json=body)})
    async with LLMClient(base_url="http://test/v1", transport=transport) as client:
        result = await client.chat(
            [{"role": "user", "content": "No power"}],
            model="qwen2.5:7b",
        )
    assert result.content == "Check the fuse."
    assert result.model == "qwen2.5:7b"


@pytest.mark.asyncio
async def test_chat_with_images_builds_data_url() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "model": "vision",
                "choices": [{"message": {"role": "assistant", "content": "board"}}],
            },
        )

    transport = httpx.MockTransport(handler)
    async with LLMClient(base_url="http://test/v1", transport=transport) as client:
        result = await client.chat_with_images(
            model="vision",
            prompt="What do you see?",
            images=[b"\xff\xd8fakejpeg"],
            system="You are a tech.",
        )
    assert result.content == "board"
    body = captured["body"]
    assert isinstance(body, dict)
    messages = body["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["content"][1]["type"] == "image_url"
    assert messages[1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
