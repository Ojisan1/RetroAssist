"""Document ingest: Markdown, PDF, and image paths → text chunks + metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm"}
PDF_SUFFIXES = {".pdf"}


@dataclass
class DocumentChunk:
    text: str
    metadata: dict[str, Any]


class IngestError(Exception):
    """Raised when a document cannot be ingested."""


def chunk_text(
    text: str,
    *,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[str]:
    """Split text into overlapping character windows (paragraph-aware)."""
    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    if not cleaned:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    overlap = max(0, min(overlap, chunk_size - 1))

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", cleaned) if p.strip()]
    if not paragraphs:
        paragraphs = [cleaned]

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = para if not current else f"{current}\n\n{para}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(para) <= chunk_size:
            current = para
            continue
        # Hard-wrap long paragraph
        start = 0
        while start < len(para):
            end = min(len(para), start + chunk_size)
            chunks.append(para[start:end])
            if end >= len(para):
                current = ""
                break
            start = max(0, end - overlap)
    if current:
        chunks.append(current)
    return chunks


def load_document_chunks(
    path: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[DocumentChunk]:
    """Load a file and return chunked text with per-chunk metadata."""
    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        raise IngestError(f"File not found: {file_path}")

    suffix = file_path.suffix.lower()
    base_meta = {
        "source": str(file_path),
        "filename": file_path.name,
        "mime": _mime_for_suffix(suffix),
    }
    if metadata:
        base_meta.update(metadata)

    if suffix in TEXT_SUFFIXES:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return _chunks_from_text(text, base_meta, chunk_size=chunk_size, overlap=overlap)

    if suffix in PDF_SUFFIXES:
        return _chunks_from_pdf(file_path, base_meta, chunk_size=chunk_size, overlap=overlap)

    if suffix in IMAGE_SUFFIXES:
        # No OCR required in Phase 4: record a discoverable image stub chunk.
        caption = (
            f"Image document: {file_path.name}. "
            f"User-imported schematic or board photo at {file_path}. "
            f"Platform tag: {base_meta.get('platform', 'unknown')}."
        )
        meta = dict(base_meta)
        meta["page"] = 1
        meta["chunk_index"] = 0
        return [DocumentChunk(text=caption, metadata=meta)]

    raise IngestError(f"Unsupported document type: {suffix}")


def _chunks_from_text(
    text: str,
    base_meta: dict[str, Any],
    *,
    chunk_size: int,
    overlap: int,
) -> list[DocumentChunk]:
    pieces = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    out: list[DocumentChunk] = []
    for idx, piece in enumerate(pieces):
        meta = dict(base_meta)
        meta["page"] = int(base_meta.get("page") or 1)
        meta["chunk_index"] = idx
        out.append(DocumentChunk(text=piece, metadata=meta))
    return out


def _chunks_from_pdf(
    path: Path,
    base_meta: dict[str, Any],
    *,
    chunk_size: int,
    overlap: int,
) -> list[DocumentChunk]:
    out: list[DocumentChunk] = []
    with fitz.open(path) as doc:
        for page_index, page in enumerate(doc):
            page_text = page.get_text("text") or ""
            page_meta = dict(base_meta)
            page_meta["page"] = page_index + 1
            page_chunks = _chunks_from_text(
                page_text,
                page_meta,
                chunk_size=chunk_size,
                overlap=overlap,
            )
            # Re-number chunk_index within page then globally later if needed
            out.extend(page_chunks)
    if not out:
        # Image-only PDF: still record a stub so ingest succeeds.
        meta = dict(base_meta)
        meta["page"] = 1
        meta["chunk_index"] = 0
        out.append(
            DocumentChunk(
                text=f"PDF document with little/no extractable text: {path.name}",
                metadata=meta,
            )
        )
    for idx, chunk in enumerate(out):
        chunk.metadata["chunk_index"] = idx
    return out


def _mime_for_suffix(suffix: str) -> str:
    return {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".txt": "text/plain",
        ".html": "text/html",
        ".htm": "text/html",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "application/octet-stream")
