"""Ingest tests for markdown, PDF-like chunking, and images."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from retroassist.rag.ingest import IngestError, chunk_text, load_document_chunks

SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "knowledge"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_chunk_text_respects_size() -> None:
    text = "word " * 500
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert chunks
    assert all(len(c) <= 100 for c in chunks)


def test_load_markdown_sample() -> None:
    path = SAMPLES / "synthetic_psu_notes.md"
    chunks = load_document_chunks(path, metadata={"platform": "synthetic-psu"})
    assert chunks
    assert any("fuse" in c.text.lower() for c in chunks)
    assert chunks[0].metadata["platform"] == "synthetic-psu"
    assert chunks[0].metadata["filename"] == "synthetic_psu_notes.md"


def test_load_image_creates_stub_chunk(tmp_path: Path) -> None:
    image_path = tmp_path / "schematic.png"
    cv2.imwrite(str(image_path), np.full((32, 32, 3), 80, dtype=np.uint8))
    chunks = load_document_chunks(image_path, metadata={"platform": "demo"})
    assert len(chunks) == 1
    assert "Image document" in chunks[0].text
    assert chunks[0].metadata["mime"] == "image/png"


def test_load_pdf(tmp_path: Path) -> None:
    import fitz

    pdf_path = tmp_path / "note.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Check the 5V regulator input capacitors.")
    doc.save(pdf_path)
    doc.close()
    chunks = load_document_chunks(pdf_path, metadata={"platform": "psu"})
    assert chunks
    assert any("5V" in c.text or "regulator" in c.text.lower() for c in chunks)
    assert chunks[0].metadata["page"] == 1


def test_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "data.bin"
    path.write_bytes(b"\x00\x01")
    with pytest.raises(IngestError, match="Unsupported"):
        load_document_chunks(path)


def test_fixture_tiny_md() -> None:
    path = FIXTURES / "knowledge" / "tiny.md"
    chunks = load_document_chunks(path)
    assert chunks and "RAG" in chunks[0].text
