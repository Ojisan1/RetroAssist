# Installation

Full interactive installer polish lands in Phase 8. Draft setup scripts are available now.

## Draft setup scripts

- Windows: `scripts/setup.ps1`
- Linux/macOS: `scripts/setup.sh`

These prompt for hardware tier and speech mode (`ptt` / `open_mic`), install the package editable with dev extras, and copy `config.example.yaml` into the platform config directory if missing.

## Manual developer install

Requires Python 3.11+.

```bash
pip install -e ".[dev]"
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv sync --extra dev
```

### Optional speech engines

Not required for mock STT/TTS, CI, or `retroassist listen --mock`. Install only for live Whisper/mic support:

```bash
pip install -e ".[speech]"
# or combine: pip install -e ".[dev,speech]"
```

Piper TTS needs an external `piper` binary and voice model path in config (see [speech.md](speech.md)).

Verify:

```bash
retroassist doctor --skip-llm
retroassist doctor
pytest
```

Config search order: built-in defaults → `%APPDATA%/RetroAssist/config.yaml` (Windows) or `~/.config/retroassist/config.yaml` (Linux) → project-root `config.yaml` → `--config` path → environment overrides (`RETROASSIST_*`).

Windows and Linux are both intended targets; Windows is the primary end-user platform.

## Cameras / OBS Virtual Camera

Configure `cameras.sources` in your config YAML (index or device name). Empty sources enable zero-camera / fixture mode for headless work.

See [live-proxy.md](live-proxy.md) for the manual YouTube → OBS → Virtual Camera testing workflow.
