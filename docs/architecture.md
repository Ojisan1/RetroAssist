# Architecture

High-level module map for RetroAssist (to be filled in as phases land):

| Module | Responsibility |
|--------|----------------|
| Capture / vision input | USB cams, capture cards, OBS Virtual Camera; multi-cam; adaptive sampling |
| Multimodal understanding | Local VLM frame analysis |
| Retrieval (RAG) | User-imported PDFs/images/notes; optional assisted web discovery |
| Reasoning / agent loop | Session context, intake, next-step suggestions, safety framing |
| Speech (STT / TTS) | Local speech in/out; PTT + continuous modes |
| User interface | Thin local UI for setup, KB management, review, session export |

Design constraints: local-first, modular, no silent scraping of copyrighted manuals, human remains fully responsible.

This document will grow as the package skeleton is implemented across Phases 1–8.
