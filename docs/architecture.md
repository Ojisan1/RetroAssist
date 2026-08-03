# Architecture

High-level module map for RetroAssist:

| Module | Responsibility | Status |
|--------|----------------|--------|
| Capture / vision input | USB cams, capture cards, OBS Virtual Camera; multi-cam; adaptive sampling | **Phase 2 implemented** |
| Multimodal understanding | Local VLM frame analysis | **Phase 3 implemented** |
| Retrieval (RAG) | User-imported PDFs/images/notes; optional assisted web discovery | **Phase 4 implemented** |
| Reasoning / agent loop | Session context, intake, next-step suggestions, safety framing | **Phase 5 implemented** |
| Text vertical slice gate | CLI session + mocked visual suite before speech/UI | **Phase 5.5 GREEN** |
| Speech (STT / TTS) | Local speech in/out; PTT + continuous modes | **Phase 6 implemented** |
| User interface | Thin local UI for setup, KB management, review, session export | **Phase 7 implemented** |

## Phase 1 foundation

- **Config** (`config.py`): defaults ← platform config dir ← project `config.yaml` ← `--config` ← `RETROASSIST_*` env
- **Model profiles** (`llm/models.py`): entry / recommended / high_end VRAM tiers
- **LLM client** (`llm/client.py`): OpenAI-compatible (Ollama) chat + vision data-URLs
- **Interfaces** (`interfaces.py`): Capture, Vision, RAG, Agent, STT, TTS protocols
- **Doctor** (`doctor.py` + CLI): local environment checks
- **Serve** (`app.py` + CLI): thin FastAPI app

## Phase 5 agent

- **Session / intake / context** — text intake, rolling measurements & steps tried
- **Loop** (`agent/loop.py`) — look_now (vision) → retrieve (RAG) → grounded suggestions
- **Safety** (`agent/safety.py`) — HV/CRT/mains cautionary framing; scrub fabricated manual pages on empty KB
- **Export** (`agent/export.py`) — markdown session logs ([session-export.md](session-export.md))
- **CI** — mocked vision + mocked agent LLM keyframe suite (PS-01…NO-KB-01)

## Phase 5.5 vertical slice gate

- **CLI** (`session` subcommands + `cli_session.py`): intake → look-now → next → export (one-shot `session run --case`)
- **Suite** (`visual_suite.py`, `tools/run_visual_suite.py`, `retroassist test-visual`): basic gate cases headless
- **Docs:** [vertical-slice.md](vertical-slice.md)

## Phase 6 speech

- **STT** (`speech/stt.py`): mock + faster-whisper; cloud only with `cloud_opt_in`
- **TTS** (`speech/tts.py`): mock + Piper CLI; `stop()` for barge-in
- **Modes** (`speech/modes.py`): PTT and open-mic + energy VAD
- **Dialogue** (`speech/dialogue.py` + `intents.py`): intent routing into the agent loop; voice latency notes
- **CLI:** `retroassist listen` (transcript / audio fixture / mock); text fallback always available
- **Docs:** [speech.md](speech.md)
- **CI:** audio fixtures under `tests/fixtures/audio/`; no live mic required

## Phase 7 thin UI

- **Routes** (`ui/routes.py` + Jinja2/HTMX templates): workbench, knowledge, settings
- **State** (`ui/state.py`): in-process agent session, voice status, fixture/camera preview
- **Serve:** `retroassist serve` → localhost UI ([ui.md](ui.md))
- **CI:** mocked FastAPI smoke + export round-trip; manual [ui-e2e-checklist.md](ui-e2e-checklist.md)

## Phase 4 knowledge / RAG

- **Ingest** (`rag/ingest.py`): Markdown/PDF/images → chunks + metadata (`source`, `page`, `platform`)
- **Store** (`rag/store.py`, `rag/knowledge.py`): Chroma persistence; empty KB → no hits
- **Retrieve** (`rag/retrieve.py`): query ± optional vision summary
- **Discovery** (`rag/discovery.py`): candidates only; `confirm_and_import` required before download/index
- **Embeddings**: default deterministic hashing (CI/offline); optional Ollama
- **Docs/samples:** [knowledge-base.md](knowledge-base.md), `samples/knowledge/` (synthetic only)

## Phase 3 vision

- **Schema** (`vision/schema.py`): structured observation + free-text fallback parsing
- **Prompts** (`vision/prompts.py`): electronics-bench multimodal JSON instructions; multi-image roles
- **Analyzer** (`vision/analyzer.py`): frames/`EncodedFrame` → VLM → observation; cache; supersede stale looks; latency fields vs 4–6s target (logged, not a hard CI gate)
- **Mock store** (`vision/mock_store.py` + `tests/fixtures/vision/responses/`): recorded VLM responses for CI keyframes

## Phase 2 capture

- **OpenCV sources** (`capture/opencv_source.py`): device enumeration (index + best-effort names), open/reconnect timeouts, OBS Virtual Camera as a normal device
- **Multi-camera** (`capture/multi_camera.py`): overview / close-up roles; zero-camera mode; fixture injection for CI
- **Hybrid sampler** (`capture/sampler.py`): continuous (~0.3–0.5 fps) / active (~1 fps), change detection, on-demand `look_now()` with JPEG encode for VLM
- **Manual live proxy:** see [live-proxy.md](live-proxy.md)

Design constraints: local-first, modular, no silent scraping of copyrighted manuals, human remains fully responsible.
