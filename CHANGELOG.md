# Changelog

All notable changes to RetroAssist are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-08-02

First public distribution bar (Phases 0–8). **Language models and speech binaries are not bundled** — install Ollama / optional `[speech]` extras separately.

### Added

- MIT-licensed Python package (`retroassist`) with argparse CLI: `doctor`, `serve`, `session`, `test-visual`, `listen`
- Config merge (platform / project / env), hardware tier model profiles, Ollama-compatible LLM client
- OpenCV capture, multi-camera roles, hybrid sampler, zero-camera / fixture path; OBS Virtual Camera as a normal capture device
- Vision analyzer with structured schema, mocked VLM store for CI, latency fields
- Chroma RAG ingest/retrieve, confirm-only discovery, hashing embeddings default (offline/CI)
- Agent loop (intake → vision → RAG → suggestions), HV/mains safety framing, markdown session export
- Text vertical-slice gate (`test-visual --basic`) with PS-01 / METER-01 / EMPTY-01 / NO-KB-01
- Speech: mock STT/TTS by default; optional faster-whisper / Piper; PTT and open-mic + VAD; intents
- Thin FastAPI + Jinja2/HTMX UI (workbench, KB confirm-import, settings, export, voice status, preview)
- Interactive installers (`scripts/setup.ps1`, `scripts/setup.sh`): tier, speech mode, base / speech / dev profiles
- Doctor checks for cameras, Ollama, and disk free space
- Docs: installation (quickstart + degradation matrix), hardware, safety, architecture, speech, UI, KB, testing

### Notes for operators

- Default UI keeps `ui.mock_agents: true` for offline serve
- `cloud_opt_in` defaults to false; cloud speech is never required
- Empty knowledge base returns no fabricated manual citations

## [0.1.0a1] — prior

Pre-alpha scaffold through Phase 7 on `master` before the Phase 8 distribution pass.
