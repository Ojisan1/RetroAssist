"""RAG package: ingest, Chroma store, retrieve, assisted discovery."""

from retroassist.rag.discovery import (
    DiscoveryCandidate,
    DiscoveryError,
    confirm_and_import,
    discover_candidates,
)
from retroassist.rag.embeddings import HashingEmbedder, OllamaEmbedder, create_embedder
from retroassist.rag.ingest import DocumentChunk, IngestError, chunk_text, load_document_chunks
from retroassist.rag.knowledge import LocalKnowledgeStore
from retroassist.rag.retrieve import retrieve
from retroassist.rag.store import VectorStore

__all__ = [
    "DiscoveryCandidate",
    "DiscoveryError",
    "DocumentChunk",
    "HashingEmbedder",
    "IngestError",
    "LocalKnowledgeStore",
    "OllamaEmbedder",
    "VectorStore",
    "chunk_text",
    "confirm_and_import",
    "create_embedder",
    "discover_candidates",
    "load_document_chunks",
    "retrieve",
]
