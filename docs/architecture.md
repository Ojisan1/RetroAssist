# Architecture

High-level module map for RetroAssist:

| Module | Responsibility | Status |
|--------|----------------|--------|
| Capture / vision input | USB cams, capture cards, OBS Virtual Camera; multi-cam; adaptive sampling | Interface only (Phase 2+) |
| Multimodal understanding | Local VLM frame analysis | Interface only (Phase 3+) |
| Retrieval (RAG) | User-imported PDFs/images/notes; optional assisted web discovery | Interface only (Phase 4+) |
| Reasoning / agent loop | Session context, intake, next-step suggestions, safety framing | Interface only (Phase 5+) |
| Speech (STT / TTS) | Local speech in/out; PTT + continuous modes | Interface only (Phase 6+) |
| User interface | Thin local UI for setup, KB management, review, session export | FastAPI `/health` stub (Phase 7+) |

## Phase 1 foundation

- **Config** (`config.py`): defaults ← platform config dir ← project `config.yaml` ← `--config` ← `RETROASSIST_*` env
- **Model profiles** (`llm/models.py`): entry / recommended / high_end VRAM tiers
- **LLM client** (`llm/client.py`): OpenAI-compatible (Ollama) chat + vision data-URLs
- **Interfaces** (`interfaces.py`): Capture, Vision, RAG, Agent, STT, TTS protocols
- **Doctor** (`doctor.py` + CLI): local environment checks
- **Serve** (`app.py` + CLI): thin FastAPI app

Design constraints: local-first, modular, no silent scraping of copyrighted manuals, human remains fully responsible.
