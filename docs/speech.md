# Speech (STT + TTS) — Phase 6

Hands-free primary I/O for the workbench. Text input remains always available.

## Install (optional for live engines)

Core RetroAssist already includes a **mock** STT/TTS path for CI and `retroassist listen --mock`. Live engines are **optional**:

```bash
# Base first (required)
pip install -e ".[dev]"

# Optional — only if you want faster-whisper + sounddevice for live STT/mic
pip install -e ".[speech]"
```

Piper TTS additionally needs the `piper` binary and a voice `.onnx` on disk (`speech.piper_voice_model`); those are separate from the pip extra.

## Modes

| Mode | Behavior |
|------|----------|
| `ptt` | Push-to-talk: capture while pressed → STT → agent → TTS |
| `open_mic` | Continuous listen with energy VAD; speech during TTS triggers **barge-in** (stops speaking) |

Configure via `speech.mode` in config (or `RETROASSIST_SPEECH_MODE`). Workshop assumes a private space; fan/solder noise may need higher `vad_energy_threshold` or a quick switch back to PTT.

## Engines

| Role | Default (CI) | Live (optional) |
|------|--------------|-----------------|
| STT | `mock` | `whisper` (faster-whisper) after optional `[speech]` extra |
| TTS | `mock` | `piper` binary + `.onnx` voice (`speech.piper_voice_model`) |

**Cloud speech** is optional and **off by default**. Set `speech.cloud_opt_in: true` and `cloud_stt_url` only when you explicitly want it. Cloud is never required.

## Intents

Parsed from transcripts:

- `look_now` — trigger vision look
- `next_step` — ask for next check
- `report_measurement` — technician measurement report
- `clarify` — short clarification / “is that in range?”
- `stop_speaking` — interrupt TTS
- `export_session` — write markdown session log

## Latency

Voice turnaround (STT→agent→TTS start/complete for mock) is logged on the session as `voice_turnaround`. Target: **&lt; 2–3 seconds** on recommended hardware when models are warm (`latency.voice_turnaround_target_seconds`).

## CLI

```bash
# Typed fallback (no mic)
retroassist listen --mock --case ps01 --transcript "What should I check next?"

# Fixture WAV + sidecar transcript (mocked STT)
retroassist listen --mock --case ps01 --audio tests/fixtures/audio/next_step.wav

# Override mode
retroassist listen --mode open_mic --mock --transcript "Stop speaking"
```

## Windows notes

- Grant microphone permission to the terminal/Python host when using live capture.
- Prefer PTT if open-mic false-triggers on tools or fans.
