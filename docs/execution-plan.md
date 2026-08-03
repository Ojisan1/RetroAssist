# RetroAssist — Execution Plan (Revised)

**Source:** `ProjectSpec.md` v0.6 + `testing-strategy.md`  
**Workspace:** `D:\Projects\RetroAssist` (spec + testing strategy only; **no Git/GitHub repo yet**)  
**Mode:** Planning only — no code until plan re-approved  

---

## Decisions Locked (user-approved)

| Decision | Choice |
|----------|--------|
| License | **MIT** |
| GitHub | **Public** from day one (`RetroAssist`) |
| Stack | **Python 3.11+**, Ollama, FastAPI (thin frontend), Chroma (or LanceDB), faster-whisper, Piper |
| OBS for v1 | **OBS Virtual Camera as capture source only**; WebSocket scene control = post-v1 |
| UI | FastAPI + **lightweight/thin** frontend (not a heavy SPA for v1) |
| Speech modes | **Both PTT and open-mic/continuous**, user-configurable; workshop assumed private / no extraneous voices |
| Sample platform | Flexible for now |
| Session export | **First-class** deliverable (clean markdown or similar session logs) |
| Early gate | **Text-only vertical slice** must pass automated visual+agent tests **before** heavy speech/UI work |

---

## 0. Spec Analysis Summary

### What we are building
A **local-first, open-source workbench assistant** for skilled electronics technicians who lack platform-specific knowledge of classic hardware. It:

1. Watches the workbench via cameras / OBS Virtual Camera  
2. Retrieves schematics and service docs (RAG)  
3. Uses multimodal LLMs to suggest next diagnostic steps and expected results  
4. Interacts primarily via **voice (STT + TTS)** — PTT or open-mic  
5. Stays useful even with **zero** imported manuals (graceful degradation)  
6. Exports clean session logs for review and expert evaluation  

### Architectural pillars (from ProjectSpec §6)
| Module | Responsibility |
|--------|----------------|
| Capture / vision input | USB cams, capture cards, OBS Virtual Camera; multi-cam; adaptive sampling |
| Multimodal understanding | Local VLM frame analysis |
| Retrieval (RAG) | User-imported PDFs/images/notes; optional assisted web discovery |
| Reasoning / agent loop | Session context, intake, next-step suggestions, safety framing |
| Speech (STT / TTS) | Local speech in/out; PTT + continuous modes |
| User interface | Thin local UI for setup, KB management, review, session export |

### Non-goals that constrain design
- No autonomous repair or instrument control  
- No SaaS / paid tiers  
- No silent scraping of copyrighted manuals  
- Human remains fully responsible (safety language mandatory)  

---

## 1. Remaining Assumptions & Non-Blocking Defaults

All major product decisions are locked above. Remaining defaults:

1. **Monorepo** Python package + thin frontend, single-process orchestrator with pluggable modules.  
2. **No GPU required to install**; VLM quality scales with hardware tiers in ProjectSpec §7.  
3. **Creator collaboration / curated datasets** = process/docs only for v1.  
4. **Private LoRA fine-tunes** = documentation hooks only in v1; full pipeline post-v1.  
5. **English only** for v1 UI/voice prompts.  
6. **Config:** `%APPDATA%/RetroAssist` (Windows) / `~/.config/retroassist` (Linux) + project-local override.  
7. **Public test data only in git;** real YouTube-derived frames under `tests/fixtures/private/` (gitignored).  
8. Move `testing-strategy.md` → `docs/testing-strategy.md` during Phase 0 (keep content; fix path).  

---

## 2. Latency Targets (explicit)

| Interaction | Target (recommended hardware tier, ~24 GB VRAM) | Notes |
|-------------|--------------------------------------------------|-------|
| **“Look now” vision analysis** | **&lt; 4–6 seconds** end-to-end | Capture → encode → VLM → structured observation available to agent |
| **Voice turnaround** (STT → agent → TTS start) | **&lt; 2–3 seconds** when possible | Depends on model size; measure and log; degrade gracefully if slower |
| Continuous background observation | ~0.3–0.5 fps (not latency-critical) | Per ProjectSpec §5.1 |
| Active probing rate | up to ~1 fps | Configurable |

These are **product targets**, not hard CI gates initially. Log p50/p95 latency in session exports and agent metrics so we can tune model size and prompt length.

---

## 3. Tech Stack (v1)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.11+ | Capture, RAG, STT, TTS, LLM clients mature |
| Packaging | `uv` or `pip` + `pyproject.toml` | Fast Windows/Linux |
| API / orchestration | FastAPI + asyncio | Modular services; WebSocket optional for live events |
| Capture | OpenCV (+ DirectShow/MediaFoundation on Windows) | USB + **OBS Virtual Camera** |
| Change detection | Frame diff / perceptual hash | Hybrid sampling |
| VLM / LLM | Ollama OpenAI-compatible API | Local-first, model-swappable |
| Embeddings | Ollama or `sentence-transformers` | Offline RAG |
| Vector store | Chroma (default) or LanceDB | Embedded, zero ops |
| PDF ingest | `pymupdf` + optional OCR | Multi-page + image schematics |
| STT | faster-whisper | Local |
| TTS | Piper | Local, low latency |
| UI | FastAPI + thin HTML/HTMX/Alpine (or minimal static JS) | Prefer thin over heavy SPA for v1 |
| Config | YAML/TOML + env | User-editable; includes `speech.mode: ptt \| open_mic` |
| Session export | Markdown (primary) | First-class; expert-evaluable |
| Installer | `scripts/setup.ps1`, `setup.sh` | Interactive |
| License | MIT | Locked |
| VCS | Git + public GitHub | Phase 0 |

---

## 4. Target Repository Layout

```
RetroAssist/
├── README.md
├── LICENSE                          # MIT
├── ProjectSpec.md
├── CONTRIBUTING.md
├── pyproject.toml
├── .gitignore                       # includes tests/fixtures/private/, models, KB data
├── .gitattributes
├── .github/workflows/ci.yml
├── scripts/
│   ├── setup.ps1
│   ├── setup.sh
│   └── dev_bootstrap.ps1
├── docs/
│   ├── hardware.md
│   ├── installation.md
│   ├── knowledge-base.md
│   ├── safety.md
│   ├── architecture.md
│   ├── testing-strategy.md          # moved from repo root
│   ├── session-export.md            # format of session logs
│   └── creator-outreach.md
├── samples/knowledge/               # public-domain / synthetic only
├── src/retroassist/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── app.py
│   ├── capture/
│   │   ├── base.py
│   │   ├── opencv_source.py         # includes OBS Virtual Camera as device
│   │   ├── multi_camera.py
│   │   └── sampler.py
│   ├── vision/
│   │   ├── analyzer.py
│   │   ├── prompts.py
│   │   └── schema.py
│   ├── rag/
│   │   ├── ingest.py
│   │   ├── store.py
│   │   ├── retrieve.py
│   │   └── discovery.py
│   ├── agent/
│   │   ├── session.py
│   │   ├── intake.py
│   │   ├── loop.py
│   │   ├── safety.py
│   │   ├── context.py
│   │   └── export.py                # session → markdown export
│   ├── speech/
│   │   ├── stt.py
│   │   ├── tts.py
│   │   ├── dialogue.py
│   │   └── modes.py                 # PTT vs open_mic
│   ├── llm/
│   │   ├── client.py
│   │   └── models.py
│   └── ui/
│       ├── static/
│       ├── templates/               # thin server-rendered or light HTMX
│       └── routes.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
│       ├── images/                  # curated public keyframes
│       │   ├── power_supply/
│       │   ├── logic_board/
│       │   ├── meter_readings/
│       │   └── empty_bench/
│       ├── queries/                 # matching queries / expected behaviors
│       ├── sessions/                # scripted full sessions
│       └── private/                 # GITIGNORED – YouTube-derived frames
└── tools/
    ├── mock_workbench.py
    └── run_visual_suite.py          # headless keyframe + agent regression runner
```

---

## 5. Testing Strategy (first-class)

**Canonical doc:** `testing-strategy.md` (repo root today → `docs/testing-strategy.md` in Phase 0).  
This section is the execution-plan integration of that document. Do not implement features without the matching test hooks.

### 5.1 Philosophy
Traditional unit tests alone are insufficient. Validate:

1. Visual understanding and grounding  
2. Agent reasoning given visual context  
3. Graceful degradation (no camera / empty KB)  
4. End-to-end session flow  
5. Safety language and uncertainty handling  

Real broken hardware is scarce → rely on **synthetic and proxy visual data**.

### 5.2 Test data rules
| Path | Committed? | Contents |
|------|------------|----------|
| `tests/fixtures/images/`, `queries/`, `sessions/` | Yes | Synthetic / public-domain / clearly licensed keyframes + queries |
| `tests/fixtures/private/` | **Never** (gitignored) | Real YouTube-derived frames for local/manual only |
| `samples/knowledge/` | Yes | Synthetic / public-domain manuals only |

### 5.3 Core automated suite: curated keyframes + queries
Each case = image(s) + technician query + optional expected behaviors (must mention X, safety language, cite retrieval, etc.).

| ID | Visual | Query | Assert (summary) |
|----|--------|-------|------------------|
| PS-01 | PSU board, blown fuse | No power; what first? | Fuse / continuity + mains safety |
| PS-02 | 5V regulator area | 0V on 5V rail | Upstream/input, caps, etc. |
| LOGIC-01 | Busy logic board | Powers on, no video | Clock/reset/video section or clarifying Qs |
| METER-01 | Meter shows 0.00V | Probing 12V rail, reading zero | Acknowledges reading; upstream checks |
| EMPTY-01 | Empty bench | What do you see? | No board visible |
| NO-KB-01 | Board + empty KB | Help diagnose Apple II | General electronics + vision; no fake manual citations |

- **CI:** unit + integration always; **small subset** of keyframe tests with **mocked/recorded VLM responses**.  
- **Local/nightly:** broader set against real Ollama when GPU available.  
- **Live proxy (manual):** YouTube repair video → OBS → Virtual Camera → RetroAssist (exploratory; not CI).

### 5.4 Full session script tests
Intake → multiple look-now → measurement reports → follow-ups → safety language. Mocked vision/STT for automation.

### 5.5 Phase ↔ test mapping

| Phase | Testing focus |
|-------|----------------|
| **0** | CI skeleton; fixture dirs; private/ gitignore |
| **1** | Config, doctor, LLM client mocks |
| **2** | Capture from webcam + OBS Virtual Camera; sampler unit tests |
| **3** | Keyframe vision analysis (mocked + optional live VLM); latency logging toward 4–6s |
| **4** | Retrieval quality on samples; empty KB; no auto-ingest policy |
| **5** | Full visual+query agent cases (table above); session export content |
| **Gate (5.5)** | **Basic automated visual+agent suite must pass** before Phase 6/7 heavy work |
| **6** | Same scenarios via voice; PTT and open-mic paths |
| **7** | Thin UI E2E; session export UX; virtual camera + text/voice |
| **8** | Clean install verification |

### 5.6 Live proxy testing (manual)
1. Play high-quality classic repair video.  
2. OBS → Virtual Camera.  
3. Point RetroAssist at that device.  
4. Text or voice queries matching on-screen content.  
Uses: continuous sampling, look-now, latency discovery, long-session tracking.

---

## 6. Vertical Slice Milestone (hard gate)

### Definition
After **Phase 1 (Foundation) + Phase 2 (Capture) + Phase 3 (Vision) + Phase 4 (RAG) + Phase 5 (Agent)** — and **before** investing heavily in Phase 6 (Speech) and Phase 7 (polished UI):

Deliver a **working text-only vertical slice** that demonstrates:

```
Camera frames (or keyframe fixtures)
    → Vision analysis
    → RAG retrieval
    → Grounded next-step suggestions (text I/O)
    → Session export (markdown)
```

**Note on phase numbering:** `testing-strategy.md` lists “Phase 1 + 2 + 4 + 5”; vision analysis is Phase 3 in this plan and is a **hard dependency** of the slice. Treat Phase 3 as in-scope for the gate.

### Gate criteria (must pass before Phase 6/7)
- [x] Basic automated visual + agent cases run headlessly: at least **PS-01, METER-01, EMPTY-01, NO-KB-01** (mocked VLM path in CI; live path locally when possible).  
- [x] Text intake works (typed symptom + notes).  
- [x] “Look now” produces an observation from capture **or** injected fixture frame.  
- [x] With sample KB ingested, suggestions can **cite retrieved content** when relevant.  
- [x] Empty KB path degrades without fabricating manual page citations.  
- [x] Safety language present on mains/HV-adjacent scenarios (e.g. PS-01).  
- [x] Session can be **exported to markdown** with intake, observations, suggestions, timestamps.  
- [x] “Look now” latency measured and logged (target &lt; 4–6s on recommended hardware; document actuals).  
- [x] Minimal text UI or CLI sufficient to run the slice (full thin web UI polish waits for Phase 7).  

**Gate status:** GREEN on mocked CI path (Phase 5.5). See [vertical-slice.md](vertical-slice.md).  
**Do not start Phase 6/7 heavy work until this gate is green.**

---

## 7. Phased Delivery Plan

### Phase 0 — Repository, OSS Scaffolding & Project Skeleton
**Goal:** Turn the empty workspace into a public MIT-licensed GitHub project with test layout and CI.

#### Deliverables / files
| Deliverable | Files |
|-------------|-------|
| Git + public GitHub remote | `.git`; `github.com/<user>/RetroAssist` (public) |
| MIT license | `LICENSE` |
| README, ignore rules | `README.md`, `.gitignore`, `.gitattributes` |
| Package skeleton | `pyproject.toml`, `src/retroassist/` minimal package |
| CI | `.github/workflows/ci.yml` (ruff + pytest) |
| Docs | Move `testing-strategy.md` → `docs/testing-strategy.md`; stubs for hardware, install, safety, architecture, session-export |
| Test tree | `tests/unit|integration|e2e|fixtures/...` including empty `fixtures/private/` + gitignore entry |
| Spec | Keep `ProjectSpec.md` |

#### Implementation steps
1. `git init` in `D:\Projects\RetroAssist`.  
2. Create **public** GitHub repo `RetroAssist` (empty remote; avoid README collision).  
3. Add **MIT** `LICENSE`.  
4. `.gitignore`: Python, venv, models, chroma/KB data, secrets, `tests/fixtures/private/`, session logs with private frames.  
5. Scaffold `pyproject.toml` (`retroassist` package, CLI entry).  
6. README: purpose, non-goals, hardware tiers, pre-alpha status, MIT, link to spec + testing strategy.  
7. Create fixture directory structure per testing strategy.  
8. Relocate testing strategy under `docs/`.  
9. CI: lint + unit tests on push.  
10. Initial commit + push to `main`.  

#### Dependencies
- GitHub account / `gh` auth  

#### Risks
- Name collision on GitHub  
- Accidental commit of private frames/manuals → strict ignore + README warning  

#### Verification
- [ ] Fresh clone shows README, MIT LICENSE, ProjectSpec, docs/testing-strategy  
- [ ] `pip install -e .` / `uv sync` works  
- [ ] CI green  
- [ ] `tests/fixtures/private/` cannot be committed (gitignore)  

---

### Phase 1 — Foundation
**Goal:** Config, interfaces, LLM client, CLI doctor, draft setup scripts.

#### Files
`config.py`, `config.example.yaml`, `llm/client.py`, `llm/models.py`, `app.py`, `__main__.py`, `scripts/setup.ps1`, `scripts/setup.sh`

#### Steps
1. Protocol/ABC interfaces: Capture, Vision, RAG, Agent, STT, TTS.  
2. Config: cameras, sampling, models, data dirs, **speech.mode (`ptt` \| `open_mic`)**, safety flags, latency logging.  
3. OpenAI-compatible LLM client (vision-capable messages); clear failure if Ollama down.  
4. Model profiles by VRAM tier (ProjectSpec §7).  
5. CLI: `retroassist serve`, `retroassist doctor`, later `retroassist test-visual`.  
6. Draft interactive setup scripts.  

#### Dependencies
Phase 0  

#### Testing
Unit: config merge, model profiles. Integration: doctor vs mock LLM.  

---

### Phase 2 — Capture & Visual Sampling
**Goal:** Multi-source frames including **OBS Virtual Camera**; hybrid sampling.

#### Files
`capture/base.py`, `opencv_source.py`, `multi_camera.py`, `sampler.py`

#### Steps
1. Enumerate devices (Windows names + indices); treat OBS VC as a normal camera device.  
2. Open/reconnect with timeouts.  
3. Multi-camera roles (overview / close-up).  
4. Hybrid sampler: 0.3–0.5 fps continuous, ~1 fps active, change detection, on-demand “look now”.  
5. Frame buffer + encode for VLM.  
6. Zero-camera mode for text-only / fixture injection (needed for CI keyframe path).  
7. Document manual live-proxy workflow (YouTube → OBS → VC).  

#### Dependencies
Phase 1  

#### Testing
- Unit: sampler + change detection fixtures  
- Manual: real webcam + OBS Virtual Camera  
- Fixture injection path for headless tests  

---

### Phase 3 — Multimodal Vision Analysis
**Goal:** Frames → structured observations; meet latency target on recommended hardware.

#### Files
`vision/analyzer.py`, `prompts.py`, `schema.py`

#### Steps
1. Multimodal prompts for electronics bench.  
2. Multi-image (overview + close-up) when available.  
3. Structured JSON output + free-text fallback.  
4. Supersede stale analysis on new look-now.  
5. Cache last analysis.  
6. **Latency instrumentation** (target &lt; 4–6s look-now).  
7. Recorded/mocked VLM response store for CI keyframe tests.  

#### Dependencies
Phase 2 (frames or fixtures); Phase 1 LLM  

#### Testing
- Keyframe fixtures: board, meter, empty bench  
- Mocked VLM regression  
- Optional live VLM latency measurement  

---

### Phase 4 — Knowledge Base & RAG
**Goal:** User import + retrieve; optional discovery with user confirm; empty-KB degradation.

#### Files
`rag/ingest.py`, `store.py`, `retrieve.py`, `discovery.py`, `docs/knowledge-base.md`, `samples/knowledge/`

#### Steps
1. Import PDF/PNG/JPG/Markdown into persistent local store.  
2. Chunk + metadata (platform, page, source).  
3. Retrieve by query + optional vision summary.  
4. Assisted discovery: candidates only; **user confirms** before import.  
5. Empty store → empty hits (no fabricated citations).  

#### Dependencies
Phase 1 (can parallelize with Phase 2)  

#### Testing
- Sample ingest + query  
- Empty KB  
- Discovery never auto-writes without confirm  
- Supports NO-KB-01 agent case  

---

### Phase 5 — Agent, Intake, Safety, Session Export
**Goal:** Fuse vision + RAG + memory into grounded next steps; export sessions.

#### Files
`agent/session.py`, `intake.py`, `loop.py`, `safety.py`, `context.py`, `export.py`, `docs/safety.md`, `docs/session-export.md`

#### Steps
1. Session intake (text first): symptom + visual notes.  
2. Combine intake + vision + RAG → suggestions (action, expected result, rationale, confidence, safety).  
3. Rolling memory of measurements and steps tried.  
4. Safety layer for HV/CRT/mains language.  
5. Longevity/mod via same loop + task tags when docs exist.  
6. **Session export to markdown** (first-class): timestamps, intake, observations, retrieval citations, suggestions, user reports, latency notes.  

#### Dependencies
Phases 3–4 (vision + RAG); fixture injection can stub capture  

#### Testing
- Full keyframe + query suite (PS-01, PS-02, LOGIC-01, METER-01, EMPTY-01, NO-KB-01)  
- Safety unit tests  
- Export content assertions  
- Scripted multi-turn session fixtures  

---

### Phase 5.5 — Vertical Slice Gate (mandatory)
**Goal:** Prove text-only path before speech/UI investment.

See **§6 Vertical Slice Milestone** and [vertical-slice.md](vertical-slice.md). Delivered:

1. CLI `retroassist session` (`intake` / `look-now` / `next` / `export` / `run`) — `cli_session.py`.  
2. `retroassist test-visual` + `tools/run_visual_suite.py` on basic suite (`visual_suite.py`).  
3. Manual smoke: fixture path required; OBS VC optional (`--no-mock`).  
4. Latency logged on observations + export; mock vs live notes in vertical-slice.md.  
5. **Go/no-go:** mocked gate GREEN → Phase 6/7 may proceed when product prioritizes them.

#### Dependencies
Phases 1–5 complete enough for gate criteria 

---

### Phase 6 — Speech (STT + TTS)
**Goal:** Hands-free primary I/O with **configurable PTT and open-mic**.

#### Files
`speech/stt.py`, `tts.py`, `dialogue.py`, `modes.py`

#### Steps
1. **Config:** `speech.mode: ptt | open_mic` (and UI toggle later).  
2. **PTT:** hold/toggle to capture utterance → STT → agent → TTS.  
3. **Open-mic:** continuous listen + VAD in private workshop assumption; barge-in stops TTS.  
4. Intents: look_now, next_step, report_measurement, clarify, stop_speaking, export_session (optional).  
5. Voice turnaround target **&lt; 2–3s** when possible; log actuals.  
6. Optional cloud speech behind explicit opt-in only.  
7. Text fallback always available.  

#### Dependencies
**Phase 5.5 gate green**; Phase 2 for look-now triggers  

#### Risks
- Fans/solder noise → tune VAD; allow quick switch to PTT  
- Windows mic permissions  

#### Testing
- Intent parsing unit tests  
- Same visual scenarios via voice transcripts  
- Manual PTT and open-mic in workshop  
- Audio fixtures for CI (no live mic required)  

---

### Phase 7 — Thin UI Integration
**Goal:** Usable local web UI for setup, KB, session, export — keep frontend thin.

#### Files
`ui/routes.py`, `ui/templates/`, `ui/static/` (minimal)

#### Steps
1. Camera preview thumbnails (low-rate).  
2. Session: transcript, suggestions, retrieval snippets.  
3. KB import + discovery confirm.  
4. Settings: cameras, models, sampling, **speech mode**.  
5. **Export session** button → markdown download/save.  
6. Voice status: listening / thinking / speaking.  
7. `retroassist serve` → localhost.  

#### Dependencies
Phase 5.5; Phase 6 optional but preferred for full UX  

#### Testing
- E2E checklist with virtual camera  
- Export round-trip  
- Mocked smoke in CI  

---

### Phase 8 — Installer, Docs, Distribution
**Goal:** ProjectSpec §9 bar for outsiders.

#### Files
Full `setup.ps1`/`setup.sh`, complete docs, CHANGELOG, tag `v0.1.0`

#### Steps
1. Interactive install: tier, models, optional STT size.  
2. Doctor validates cameras, Ollama, disk.  
3. Quickstart including mock/fixture mode without GPU.  
4. Document degradation matrix + latency expectations.  
5. Public GitHub release notes (models not bundled).  

#### Testing
Clean Windows install from docs only.  

---

### Phase 9 — Post-v1 (not required for initial success)
- OBS WebSocket scene control  
- Broader keyframe library (Apple II, C64, arcade, …)  
- Scope waveform tests  
- Community knowledge packs (licensed)  
- Private LoRA training guide  
- Creator beta invites  

---

## 8. Dependency Graph (revised)

```
Phase 0  Public GitHub + MIT + test fixture layout + CI
    ↓
Phase 1  Foundation (config, LLM, interfaces, doctor)
    ↓
    ├───────────────┬────────────────┐
    ↓               ↓                ↓
Phase 2 Capture  Phase 4 RAG    (speech later)
    ↓               ↓
Phase 3 Vision ─────┤
                    ↓
              Phase 5 Agent + safety + session export
                    ↓
              ★ Phase 5.5 VERTICAL SLICE GATE ★
                 (text path + basic keyframe suite)
                    ↓
              Phase 6 Speech (PTT + open_mic)
                    ↓
              Phase 7 Thin UI polish
                    ↓
              Phase 8 Installer + docs + v0.1
```

### Why this order
1. Repo/public MIT first → collaboration and CI.  
2. Interfaces before features → less rework.  
3. Capture ∥ RAG after foundation → agent inputs ready.  
4. Vision then agent → vertical slice.  
5. **Hard gate** before speech/UI → avoid polishing the wrong I/O.  
6. Speech before full UI polish → primary workbench mode; thin UI still enough for setup/export.  

---

## 9. Risk Register

| Risk | Mitigation |
|------|------------|
| VLM hallucinates pins/pages | Cite retrieval; empty-KB rules; human-responsible framing |
| Copyrighted manuals/videos | User import only; no bundled commercial manuals; private fixtures gitignored |
| Latency misses targets | Measure early; smaller models; shorter prompts; async UI |
| Open-mic false triggers | Configurable PTT fallback; VAD tuning; workshop assumption documented |
| Scope creep | Vertical slice gate; post-v1 list explicit |
| No GitHub yet | Phase 0 first |

---

## 10. Success Criteria Mapping (ProjectSpec §11)

| Criterion | Measure |
|-----------|---------|
| Less manual study up front | Intake + first suggestions quickly via text slice, then voice |
| Grounded in visual + docs | Keyframe suite + retrieval citations |
| Primarily voice | Phase 6 PTT + open_mic full exchange |
| Expert evaluable | **Session markdown export** + reproducible fixture cases |
| Documented OSS on Windows | Public repo, MIT, install docs, clean install test |
| Preservation impact | Qualitative / later creator feedback |

---

## 11. Overall Approach

Build RetroAssist as a **modular local Python system**: capture (including OBS Virtual Camera) → vision → RAG → agent, with **session export** and a **hard text-only vertical slice gate** proven by **keyframe + query regression tests** before speech and UI polish. Speech supports **both PTT and open-mic**. Stay local-first, MIT-licensed, public on GitHub, permission-first on documentation, and honest about uncertainty and safety.

---

## 12. First Concrete Next Steps (approve to execute)

1. **Phase 0**  
   - `git init`  
   - Create **public** GitHub repo `RetroAssist`  
   - Add **MIT** `LICENSE`, `README.md`, `.gitignore` (incl. `tests/fixtures/private/`), `.gitattributes`  
   - Scaffold `pyproject.toml` + `src/retroassist`  
   - Create `tests/` tree per testing strategy  
   - Move `testing-strategy.md` → `docs/testing-strategy.md`  
   - CI stub; initial commit + push  
2. **Phase 1** — config, LLM client, interfaces, `doctor`, draft setup.  
3. **Phases 2 ∥ 4**, then **3 → 5 → 5.5 gate**, then **6 → 7 → 8**.  

No application feature work until Phase 0 is approved for execution.
