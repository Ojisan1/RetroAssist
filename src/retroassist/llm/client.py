"""OpenAI-compatible LLM client (Ollama and similar local servers)."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx


class LLMError(Exception):
    """Base error for LLM client failures."""


class LLMUnavailableError(LLMError):
    """Raised when the OpenAI-compatible endpoint cannot be reached."""


class LLMResponseError(LLMError):
    """Raised when the endpoint returns an unexpected or error response."""


@dataclass(frozen=True)
class ChatMessage:
    """Simple chat message; content may be plain text or multimodal parts."""

    role: str
    content: str | list[dict[str, Any]]


@dataclass(frozen=True)
class ChatResult:
    """Normalized chat completion result."""

    content: str
    model: str
    raw: dict[str, Any]


class LLMClient:
    """Thin OpenAI-compatible Chat Completions client (vision-capable)."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434/v1",
        api_key: str = "ollama",
        timeout_seconds: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> LLMClient:
        self._client = self._build_client()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout_seconds,
            transport=self._transport,
        )

    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> dict[str, Any]:
        """Probe the server. Raises LLMUnavailableError if Ollama/API is down."""
        client = self._require_client()
        try:
            # Prefer OpenAI-compatible models list; fall back to Ollama native tags.
            response = await client.get("/models")
            if response.status_code == 404:
                # Native Ollama tags API lives outside /v1.
                response = await self._ollama_tags()
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(
                f"LLM server unreachable at {self.base_url}: {exc}. "
                "Is Ollama running? Start it and verify the base_url in config."
            ) from exc
        try:
            return response.json()
        except ValueError as exc:
            raise LLMResponseError("LLM health endpoint returned non-JSON") from exc

    def _native_base(self) -> str:
        """Derive Ollama native base (strip trailing /v1)."""
        base = self.base_url
        if base.endswith("/v1"):
            return base[:-3]
        return base

    async def _ollama_tags(self) -> httpx.Response:
        """GET /api/tags on the native Ollama port (not under /v1)."""
        native = self._native_base()
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self._transport,
        ) as raw:
            return await raw.get(f"{native}/api/tags")

    async def list_models(self) -> list[str]:
        """Return available model names/ids if the server exposes them."""
        payload = await self.health_check()
        models = payload.get("data") or payload.get("models") or []
        names: list[str] = []
        for item in models:
            if isinstance(item, dict):
                name = item.get("id") or item.get("name") or item.get("model")
                if name:
                    names.append(str(name))
            elif isinstance(item, str):
                names.append(item)
        return names

    async def chat(
        self,
        messages: Sequence[ChatMessage | dict[str, Any]],
        *,
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """Send a chat completion request (text or vision message parts)."""
        client = self._require_client()
        normalized = [_message_to_dict(m) for m in messages]
        body: dict[str, Any] = {
            "model": model,
            "messages": normalized,
            "temperature": temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        try:
            response = await client.post("/chat/completions", json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(
                f"Chat request failed against {self.base_url}: {exc}. "
                "Is Ollama running and is the model pulled?"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMResponseError("Chat completion returned non-JSON") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(f"Unexpected chat completion shape: {data!r}") from exc

        if not isinstance(content, str):
            content = str(content)

        return ChatResult(content=content, model=str(data.get("model", model)), raw=data)

    async def chat_with_images(
        self,
        *,
        model: str,
        prompt: str,
        images: Sequence[bytes],
        system: str | None = None,
        mime_type: str = "image/jpeg",
    ) -> ChatResult:
        """Convenience helper for vision prompts using data-URL images."""
        messages: list[ChatMessage] = []
        if system:
            messages.append(ChatMessage(role="system", content=system))

        parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image_bytes in images:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                }
            )
        messages.append(ChatMessage(role="user", content=parts))
        return await self.chat(messages, model=model)


def _message_to_dict(message: ChatMessage | dict[str, Any]) -> dict[str, Any]:
    if isinstance(message, ChatMessage):
        return {"role": message.role, "content": message.content}
    return message
