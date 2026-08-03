"""KnowledgeStore implementation over Chroma + ingest/retrieve helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from retroassist.config import AppConfig
from retroassist.interfaces import KnowledgeStore
from retroassist.rag.embeddings import Embedder, create_embedder
from retroassist.rag.ingest import IngestError, load_document_chunks
from retroassist.rag.retrieve import retrieve as retrieve_from_store
from retroassist.rag.store import VectorStore


class LocalKnowledgeStore(KnowledgeStore):
    """Persistent local knowledge base (Chroma). Empty store returns no hits."""

    def __init__(
        self,
        persist_dir: Path,
        *,
        embedder: Embedder | None = None,
        chunk_size: int = 800,
        overlap: int = 100,
        collection_name: str = "retroassist_kb",
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.store = VectorStore(
            self.persist_dir,
            collection_name=collection_name,
            embedder=embedder,
        )

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        embedder: Embedder | None = None,
    ) -> LocalKnowledgeStore:
        rag = config.raw.get("rag") or {}
        persist = rag.get("persist_dir")
        if persist:
            persist_dir = Path(str(persist)).expanduser()
            if not persist_dir.is_absolute():
                persist_dir = config.config_dir / persist_dir
        else:
            persist_dir = config.resolve_data_path("knowledge_base") / "chroma"

        if embedder is None:
            embedder = create_embedder(
                str(rag.get("embedding_provider", "hashing")),
                dimensions=int(rag.get("embedding_dimensions", 384)),
                model=config.resolved_models().get("embedding"),
                base_url=config.llm_base_url,
                api_key=config.llm_api_key,
            )
        return cls(
            persist_dir,
            embedder=embedder,
            chunk_size=int(rag.get("chunk_size", 800)),
            overlap=int(rag.get("chunk_overlap", 100)),
            collection_name=str(rag.get("collection_name", "retroassist_kb")),
        )

    @property
    def count(self) -> int:
        return self.store.count

    async def ingest(self, path: str, *, metadata: dict[str, Any] | None = None) -> int:
        try:
            chunks = load_document_chunks(
                path,
                metadata=metadata,
                chunk_size=self.chunk_size,
                overlap=self.overlap,
            )
        except IngestError:
            raise
        return self.store.add_chunks(
            [c.text for c in chunks],
            [c.metadata for c in chunks],
        )

    async def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
        vision_summary: str | None = None,
    ) -> list[dict[str, Any]]:
        return retrieve_from_store(
            self.store,
            query,
            limit=limit,
            vision_summary=vision_summary,
        )
