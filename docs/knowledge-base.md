# Knowledge Base

RetroAssist keeps schematics, manuals, and notes in a **local** Chroma-backed store.

## Import (primary path)

Users supply their own documentation:

- Markdown / plain text (`.md`, `.txt`, `.html`)
- PDF (`.pdf`) via PyMuPDF text extraction
- Images (`.png`, `.jpg`, …) recorded as discoverable stub chunks (OCR is optional/future)

Config defaults:

- Persist dir: `%APPDATA%/RetroAssist/knowledge/chroma` (Windows) or `~/.config/retroassist/knowledge/chroma`
- Embedding provider: `hashing` (deterministic, offline) or `ollama`
- Chunk size / overlap: see `rag` in `config.example.yaml`

Programmatic import:

```python
from retroassist.config import load_config
from retroassist.rag import LocalKnowledgeStore

cfg = load_config()
kb = LocalKnowledgeStore.from_config(cfg)
await kb.ingest("path/to/notes.md", metadata={"platform": "synthetic-psu"})
hits = await kb.retrieve("blown fuse continuity", limit=3)
```

## Empty knowledge base

An empty store returns **no retrieval hits** (`[]`). The system must not invent manual page citations. This underpins the later NO-KB-01 agent behavior (Phase 5).

## Assisted discovery (optional)

`discover_candidates(platform)` returns a short list of promising sources (title, URL, reason). Preferred domains include Internet Archive and Bitsavers.

**Nothing is downloaded or indexed until the user confirms** via `confirm_and_import(...)`. Silent scraping / auto-ingest of copyrighted manuals is forbidden.

## Samples

`samples/knowledge/` contains **synthetic** notes for demos and tests only — not real manufacturer manuals.
