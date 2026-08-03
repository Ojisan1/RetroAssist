"""Embedding providers for RAG (deterministic local + optional Ollama)."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx
import numpy as np


class Embedder(Protocol):
    """Produces fixed-size vectors for text documents/queries."""

    @property
    def dimensions(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class HashingEmbedder:
    """Deterministic bag-of-tokens hashing embedder (offline / CI-safe)."""

    def __init__(self, dimensions: int = 384) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be >= 8")
        self._dimensions = int(dimensions)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        vec = np.zeros(self._dimensions, dtype=np.float64)
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            tokens = ["empty"]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            # Use two uint32s to pick index and signed weight
            idx = int.from_bytes(digest[0:4], "little") % self._dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vec[idx] += sign * weight
        norm = float(np.linalg.norm(vec))
        if norm <= 0:
            return vec.tolist()
        return (vec / norm).tolist()


class OllamaEmbedder:
    """OpenAI-compatible or native Ollama embeddings endpoint."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434/v1",
        model: str = "nomic-embed-text",
        api_key: str = "ollama",
        timeout_seconds: float = 60.0,
        dimensions: int = 768,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._dimensions = dimensions
        self._transport = transport

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        with httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout_seconds,
            transport=self._transport,
        ) as client:
            response = client.post(
                "/embeddings",
                json={"model": self.model, "input": text},
            )
            response.raise_for_status()
            data = response.json()
            vector = data["data"][0]["embedding"]
            self._dimensions = len(vector)
            return [float(x) for x in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def create_embedder(
    provider: str = "hashing",
    *,
    dimensions: int = 384,
    model: str | None = None,
    base_url: str = "http://127.0.0.1:11434/v1",
    api_key: str = "ollama",
) -> Embedder:
    """Factory for configured embedding providers."""
    name = provider.strip().lower()
    if name in {"hash", "hashing", "local", "deterministic"}:
        return HashingEmbedder(dimensions=dimensions)
    if name in {"ollama", "openai", "openai_compatible"}:
        return OllamaEmbedder(
            base_url=base_url,
            model=model or "nomic-embed-text",
            api_key=api_key,
            dimensions=dimensions,
        )
    raise ValueError(f"Unknown embedding provider {provider!r}")
