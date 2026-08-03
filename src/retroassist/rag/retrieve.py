"""Retrieval helpers over the knowledge vector store."""

from __future__ import annotations

from typing import Any

from retroassist.rag.store import VectorStore


def retrieve(
    store: VectorStore,
    query: str,
    *,
    limit: int = 5,
    vision_summary: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve ranked chunks. Empty store always returns [].

    When ``vision_summary`` is provided, it is appended to the query to bias
    retrieval toward the current visual context without fabricating hits.
    """
    if store.is_empty():
        return []
    parts = [query.strip()]
    if vision_summary and vision_summary.strip():
        parts.append(f"Visual context: {vision_summary.strip()}")
    combined = "\n".join(p for p in parts if p)
    if not combined:
        return []
    return store.query(combined, limit=limit)
