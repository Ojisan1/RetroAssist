# Installation

Windows is the primary end-user platform; Linux is also supported. **Models are never bundled** — install Ollama and pull models only when you want live inference.

## Quickstart (no GPU / mock path)

Useful for first install, CI-like smoke, and docs verification without cameras or Ollama.

```powershell
# Windows (from a clone of the repo)
git clone https://github.com/Ojisan1/RetroAssist.git
cd RetroAssist
python -m pip install -e .
retroassist doctor --skip-llm
retroassist test-visual --basic
retroassist session run --case ps01 --out session.md --mock
retroassist serve
```

```bash
# Linux / macOS
git clone https://github.com/Ojisan1/RetroAssist.git
cd RetroAssist
python3 -m pip install -e .
retroassist doctor --skip-llm
retroassist test-visual --basic
retroassist session run --case ps01 --out session.md --mock
retroassist serve
```

Open http://127.0.0.1:8765 — UI defaults keep agents mocked (`ui.mock_agents: true`) for offline use.

Optional interactive installer (prompts for hardware tier, speech mode, install profile):

- Windows: `powershell -ExecutionPolicy Bypass -File scripts/setup.ps1`
- Linux/macOS: `bash scripts/setup.sh`

Default profile is **base** (runtime only). Choose `base+speech` for optional Whisper/mic deps, or `dev` for pytest/ruff.

## Clean Windows install checklist (docs-only)

Use this to verify a fresh machine can reach a working mock workbench from documentation alone:

1. Install [Python 3.11+](https://www.python.org/downloads/) and ensure `python` is on PATH.
2. Clone the repo; run `python -m pip install -e .` (or `scripts/setup.ps1`).
3. `retroassist doctor --skip-llm` → Overall PASS (cameras/Ollama may be absent; disk ≥ 1 GiB free).
4. `retroassist test-visual --basic` → GATE PASS.
5. `retroassist serve` → open the UI; export a mock session.
6. (Optional live) Install [Ollama](https://ollama.com/), pull tier models (below), then `retroassist doctor` without `--skip-llm`.

## Live models (optional)

1. Install and start Ollama.
2. Pull models for your hardware tier (names from `src/retroassist/llm/models.py`):

| Tier | Vision | LLM | Embedding |
|------|--------|-----|-----------|
| entry (12–16 GB) | `qwen2.5vl:7b` | `qwen2.5:7b` | `nomic-embed-text` |
| recommended (~24 GB) | `qwen2.5vl:11b` | `qwen2.5:14b` | `nomic-embed-text` |
| high_end (32 GB+) | `qwen2.5vl:32b` | `qwen2.5:32b` | `nomic-embed-text` |

```bash
ollama pull qwen2.5vl:11b
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

3. Set `models.tier` in config (or use the setup script). Override individual names under `models:` if needed.
4. Run `retroassist doctor` (no `--skip-llm`) to confirm reachability and pulled tags.
5. For real VLM/agent in the UI, set `ui.mock_agents: false`.

See [hardware.md](hardware.md) for VRAM guidance and [live-proxy.md](live-proxy.md) for OBS Virtual Camera.

## Optional speech engines

Not required for mock STT/TTS, CI, `listen --mock`, or the installer base profile:

```bash
pip install -e ".[speech]"
```

Piper TTS needs an external `piper` binary and `speech.piper_voice_model` path — see [speech.md](speech.md). Cloud STT remains opt-in (`cloud_opt_in: false` by default) and is never required.

## Contributor install

```bash
pip install -e ".[dev]"
# or: pip install -e ".[dev,speech]"
ruff check .
pytest
```

With [uv](https://github.com/astral-sh/uv): `uv sync --extra dev`.

## Configuration

Config search order: built-in defaults → `%APPDATA%/RetroAssist/config.yaml` (Windows) or `~/.config/retroassist/config.yaml` (Linux) → project-root `config.yaml` → `--config` path → `RETROASSIST_*` environment overrides.

Copy [config.example.yaml](../config.example.yaml) into the platform directory if you are not using the setup script.

`retroassist doctor` checks Python, config, model tier, speech settings, **disk free space**, capture/OpenCV, cameras (zero-camera OK), RAG store, and optionally Ollama.

## Degradation matrix

RetroAssist stays usable as capabilities drop. Empty knowledge or missing hardware never fabricates manual citations.

| Condition | What still works | What changes |
|-----------|------------------|--------------|
| No GPU / no Ollama | Install, doctor `--skip-llm`, mocked visual suite, `session --mock`, UI with `ui.mock_agents: true` | No live VLM/LLM; pull models later for live path |
| No camera | Fixture/zero-camera mode; inject keyframes via CLI or UI fixtures | No live preview from USB/OBS VC |
| Empty knowledge base | Vision + general electronics suggestions; retrieval returns `[]` | No schematic page citations (NO-KB path) |
| Mock speech only | Intents + dialogue via `--mock` / default providers | No live mic or Piper playback until `[speech]` + engines |
| Ollama up, models missing | Doctor reports `llm.models_pulled` FAIL with missing tags | Pull missing tags; rest of stack unchanged |
| Low disk (&lt; ~1 GiB free on data volume) | Doctor `disk` FAIL | Free space under platform data dirs before ingesting KB |

## Latency expectations

| Interaction | Target (recommended ~24 GB VRAM tier) | Notes |
|-------------|----------------------------------------|-------|
| Look-now (capture → VLM → observation) | &lt; 4–6 s | Logged on observations + session export; mock path is sub-second overhead only |
| Voice turnaround (STT → agent → TTS start) | &lt; 2–3 s when possible | Depends on model size; degrade gracefully |

These are product targets, not hard CI gates. See [vertical-slice.md](vertical-slice.md) and config `latency.*` fields.

## Cameras / OBS Virtual Camera

Configure `cameras.sources` in YAML (index or device name such as `OBS Virtual Camera`). Empty `sources` enables zero-camera / fixture mode.

## Knowledge bases

Import PDFs/images/notes yourself; discovery never auto-ingests without confirm. See [knowledge-base.md](knowledge-base.md) and [safety.md](safety.md).
