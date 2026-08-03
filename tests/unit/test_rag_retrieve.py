"""Retrieve + empty-KB behavior tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from retroassist.config import load_config
from retroassist.rag.embeddings import HashingEmbedder
from retroassist.rag.knowledge import LocalKnowledgeStore

SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "knowledge"


@pytest.mark.asyncio
async def test_empty_kb_returns_no_hits(tmp_path: Path) -> None:
    store = LocalKnowledgeStore(tmp_path / "chroma", embedder=HashingEmbedder(64))
    hits = await store.retrieve("anything at all")
    assert hits == []
    assert store.count == 0


@pytest.mark.asyncio
async def test_ingest_and_retrieve_sample(tmp_path: Path) -> None:
    store = LocalKnowledgeStore(tmp_path / "chroma", embedder=HashingEmbedder(128))
    n = await store.ingest(
        str(SAMPLES / "synthetic_psu_notes.md"),
        metadata={"platform": "synthetic-psu"},
    )
    assert n >= 1
    hits = await store.retrieve("blown fuse continuity", limit=3)
    assert hits
    assert any("fuse" in h["text"].lower() for h in hits)
    assert hits[0]["source"]
    assert "score" in hits[0]


@pytest.mark.asyncio
async def test_retrieve_with_vision_summary(tmp_path: Path) -> None:
    store = LocalKnowledgeStore(tmp_path / "chroma", embedder=HashingEmbedder(128))
    await store.ingest(str(SAMPLES / "synthetic_logic_notes.md"), metadata={"platform": "logic"})
    hits = await store.retrieve(
        "no video",
        vision_summary="Busy logic board with many ICs visible.",
        limit=3,
    )
    assert hits
    assert any("video" in h["text"].lower() or "clock" in h["text"].lower() for h in hits)


@pytest.mark.asyncio
async def test_from_config_persist_path(tmp_path: Path) -> None:
    cfg = load_config(project_root=tmp_path, platform_dir=tmp_path / "platform")
    store = LocalKnowledgeStore.from_config(cfg, embedder=HashingEmbedder(32))
    assert "chroma" in str(store.persist_dir).replace("\\", "/")
    assert await store.retrieve("x") == []
