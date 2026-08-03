"""Chroma-backed persistent knowledge store."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from chromadb import Documents, EmbeddingFunction, Embeddings, PersistentClient

from retroassist.rag.embeddings import Embedder, HashingEmbedder


class ChromaEmbeddingAdapter(EmbeddingFunction):
    """Adapt RetroAssist Embedder to Chroma's EmbeddingFunction protocol."""

    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder

    @staticmethod
    def name() -> str:
        return "retroassist_embedder"

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 - chroma API
        return self.embedder.embed_documents(list(input))


class VectorStore:
    """Thin persistent Chroma collection wrapper."""

    def __init__(
        self,
        persist_dir: Path,
        *,
        collection_name: str = "retroassist_kb",
        embedder: Embedder | None = None,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.embedder = embedder or HashingEmbedder()
        self._client = PersistentClient(path=str(self.persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=ChromaEmbeddingAdapter(self.embedder),
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        return int(self._collection.count())

    def is_empty(self) -> bool:
        return self.count == 0

    def add_chunks(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]],
        *,
        ids: list[str] | None = None,
    ) -> int:
        if not texts:
            return 0
        if len(texts) != len(metadatas):
            raise ValueError("texts and metadatas length mismatch")
        chunk_ids = ids or [str(uuid.uuid4()) for _ in texts]
        # Chroma metadata values must be scalar
        clean_meta = [_sanitize_metadata(m) for m in metadatas]
        self._collection.add(documents=texts, metadatas=clean_meta, ids=chunk_ids)
        return len(texts)

    def query(
        self,
        text: str,
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        if self.is_empty() or not text.strip():
            return []
        n = max(1, min(int(limit), self.count))
        result = self._collection.query(query_texts=[text], n_results=n)
        return _format_query_result(result)

    def reset(self) -> None:
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=ChromaEmbeddingAdapter(self.embedder),
            metadata={"hnsw:space": "cosine"},
        )


def _sanitize_metadata(meta: dict[str, Any]) -> dict[str, str | int | float | bool]:
    clean: dict[str, str | int | float | bool] = {}
    for key, value in meta.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[str(key)] = value
        else:
            clean[str(key)] = str(value)
    return clean


def _format_query_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    ids = (result.get("ids") or [[]])[0]
    hits: list[dict[str, Any]] = []
    for idx, doc in enumerate(documents):
        distance = float(distances[idx]) if idx < len(distances) else 0.0
        # cosine distance → similarity-ish score
        score = 1.0 - distance
        meta = metadatas[idx] if idx < len(metadatas) else {}
        hits.append(
            {
                "id": ids[idx] if idx < len(ids) else "",
                "text": doc,
                "score": score,
                "metadata": dict(meta or {}),
                "source": (meta or {}).get("source"),
                "page": (meta or {}).get("page"),
                "platform": (meta or {}).get("platform"),
            }
        )
    return hits
