"""Discovery: candidates only; confirm required before import."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from retroassist.rag.discovery import (
    DiscoveryCandidate,
    confirm_and_import,
    discover_candidates,
)
from retroassist.rag.embeddings import HashingEmbedder
from retroassist.rag.store import VectorStore

SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "knowledge"


@pytest.mark.asyncio
async def test_discover_does_not_write_to_store(tmp_path: Path) -> None:
    store = VectorStore(tmp_path / "chroma", embedder=HashingEmbedder(32))
    assert store.is_empty()

    async def fake_search(platform: str, limit: int):
        return [
            DiscoveryCandidate(
                title=f"{platform} Archive hit",
                source_url="https://archive.org/details/fake",
                reason="Preferred domain",
                domain="archive.org",
                score=1.0,
            )
        ]

    candidates = await discover_candidates("Apple II", search_fn=fake_search)
    assert candidates
    assert candidates[0].domain == "archive.org"
    assert store.is_empty()


@pytest.mark.asyncio
async def test_seed_candidates_when_remote_fails() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    async with httpx.AsyncClient(transport=transport) as client:
        candidates = await discover_candidates("Commodore 64", http_client=client)
    assert any(c.domain == "archive.org" for c in candidates)
    assert any(c.domain == "bitsavers.org" for c in candidates)


@pytest.mark.asyncio
async def test_confirm_and_import_writes(tmp_path: Path) -> None:
    store = VectorStore(tmp_path / "chroma", embedder=HashingEmbedder(64))
    sample = (SAMPLES / "synthetic_psu_notes.md").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sample,
            headers={"content-type": "text/markdown"},
        )

    candidate = DiscoveryCandidate(
        title="Synthetic PSU notes",
        source_url="https://example.com/synthetic_psu_notes.md",
        reason="User confirmed test import",
        domain="example.com",
        score=1.0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        added = await confirm_and_import(
            candidate,
            store,
            dest_dir=tmp_path / "downloads",
            metadata={"platform": "synthetic-psu"},
            http_client=client,
        )
    assert added >= 1
    assert not store.is_empty()
    hits = store.query("fuse continuity", limit=3)
    assert hits
