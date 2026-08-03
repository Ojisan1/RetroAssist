"""Assisted documentation discovery (candidates only; confirm before import)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from retroassist.rag.ingest import load_document_chunks
from retroassist.rag.store import VectorStore

PREFERRED_DOMAINS = (
    "archive.org",
    "bitsavers.org",
    "datamath.org",
    "manualslib.com",
    "minuszerodegrees.net",
    "github.com",
)


@dataclass(frozen=True)
class DiscoveryCandidate:
    title: str
    source_url: str
    reason: str
    domain: str
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SearchFn = Callable[[str, int], Awaitable[list[DiscoveryCandidate]]]


class DiscoveryError(Exception):
    """Raised when discovery or confirmed import fails."""


async def discover_candidates(
    platform: str,
    *,
    limit: int = 5,
    search_fn: SearchFn | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> list[DiscoveryCandidate]:
    """Return promising documentation candidates. Does **not** ingest anything."""
    query = platform.strip()
    if not query:
        return []
    if search_fn is not None:
        return await search_fn(query, limit)

    # Default: curated static seeds + optional DuckDuckGo HTML-lite search.
    seeded = _seed_candidates(query)
    remote: list[DiscoveryCandidate] = []
    try:
        remote = await _duckduckgo_candidates(query, limit=limit, client=http_client)
    except Exception:  # noqa: BLE001 - discovery must degrade gracefully
        remote = []
    merged = _merge_and_rank(seeded + remote, limit=limit)
    return merged


async def confirm_and_import(
    candidate: DiscoveryCandidate,
    store: VectorStore,
    *,
    dest_dir: Path,
    metadata: dict[str, Any] | None = None,
    http_client: httpx.AsyncClient | None = None,
    chunk_size: int = 800,
    overlap: int = 100,
) -> int:
    """Download a user-confirmed candidate and ingest it into the local store.

    This is the only path that writes discovered remote content into the KB.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    own_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=60.0, follow_redirects=True)
    try:
        response = await client.get(candidate.source_url)
        response.raise_for_status()
        filename = _filename_for_candidate(candidate, response)
        path = dest_dir / filename
        path.write_bytes(response.content)
    except httpx.HTTPError as exc:
        raise DiscoveryError(f"Failed to download {candidate.source_url}: {exc}") from exc
    finally:
        if own_client:
            await client.aclose()

    meta = {
        "platform": metadata.get("platform") if metadata else None,
        "discovered_from": candidate.source_url,
        "title": candidate.title,
    }
    if metadata:
        meta.update(metadata)
    chunks = load_document_chunks(
        path,
        metadata={k: v for k, v in meta.items() if v is not None},
        chunk_size=chunk_size,
        overlap=overlap,
    )
    return store.add_chunks(
        [c.text for c in chunks],
        [c.metadata for c in chunks],
    )


def _seed_candidates(platform: str) -> list[DiscoveryCandidate]:
    """Offline-safe starting points (manual confirmation still required to import)."""
    slug = platform.replace(" ", "+")
    return [
        DiscoveryCandidate(
            title=f"{platform} manuals on Internet Archive",
            source_url=f"https://archive.org/search?query={slug}+manual",
            reason="Prefer Internet Archive for historical service manuals and schematics.",
            domain="archive.org",
            score=0.9,
        ),
        DiscoveryCandidate(
            title=f"{platform} docs on Bitsavers",
            source_url="https://bitsavers.org/",
            reason="Bitsavers hosts scanned classic computing documentation.",
            domain="bitsavers.org",
            score=0.85,
        ),
    ]


async def _duckduckgo_candidates(
    platform: str,
    *,
    limit: int,
    client: httpx.AsyncClient | None,
) -> list[DiscoveryCandidate]:
    """Best-effort lightweight search; may return empty if network/blocked."""
    own = client is None
    http = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        query = f"{platform} service manual schematic"
        response = await http.get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "RetroAssist/0.1 (local knowledge discovery)"},
        )
        response.raise_for_status()
        return _parse_ddg_html(response.text, limit=limit)
    finally:
        if own:
            await http.aclose()


def _parse_ddg_html(html: str, *, limit: int) -> list[DiscoveryCandidate]:
    # Minimal href scrape without adding BeautifulSoup dependency.
    import re

    pattern = re.compile(
        r'uddg=([^&"]+).*?class="result__a"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    # Fallback simpler pattern for result links
    simple = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    found: list[DiscoveryCandidate] = []
    for match in simple.finditer(html):
        url = match.group(1)
        title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        if not url.startswith("http"):
            continue
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        score = 0.5 + (0.4 if any(domain.endswith(d) for d in PREFERRED_DOMAINS) else 0.0)
        found.append(
            DiscoveryCandidate(
                title=title or domain,
                source_url=url,
                reason=_reason_for_domain(domain),
                domain=domain,
                score=score,
            )
        )
        if len(found) >= limit:
            break
    if found:
        return found
    # pattern reserved for future uddg decoding; keep for clarity
    _ = pattern
    return found


def _reason_for_domain(domain: str) -> str:
    if any(domain.endswith(d) for d in PREFERRED_DOMAINS):
        return f"Matches preferred technical archive domain ({domain})."
    return f"Search result from {domain}; user must review before import."


def _merge_and_rank(
    candidates: list[DiscoveryCandidate],
    *,
    limit: int,
) -> list[DiscoveryCandidate]:
    seen: set[str] = set()
    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
    out: list[DiscoveryCandidate] = []
    for cand in ranked:
        key = cand.source_url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
        if len(out) >= limit:
            break
    return out


def _filename_for_candidate(candidate: DiscoveryCandidate, response: httpx.Response) -> str:
    path_name = Path(urlparse(candidate.source_url).path).name
    if path_name and "." in path_name:
        return path_name
    content_type = response.headers.get("content-type", "")
    if "pdf" in content_type:
        return "discovered.pdf"
    if "html" in content_type:
        return "discovered.html"
    return "discovered.bin"
