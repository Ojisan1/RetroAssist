#!/usr/bin/env bash
# Draft interactive setup for RetroAssist (Phase 1)
# Full installer polish lands in Phase 8.

set -euo pipefail

echo "RetroAssist setup (draft)"
echo "========================="

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found on PATH. Install Python 3.11+ and re-run." >&2
  exit 1
fi

PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Detected Python ${PYVER}"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' || {
  echo "Python 3.11+ is required." >&2
  exit 1
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo
echo "Hardware tier (affects default model names):"
echo "  1) entry       (12-16 GB VRAM)"
echo "  2) recommended (24 GB VRAM)  [default]"
echo "  3) high_end    (32 GB+ VRAM)"
read -r -p "Choose tier [1-3]: " TIER_CHOICE
case "${TIER_CHOICE:-2}" in
  1) TIER="entry" ;;
  3) TIER="high_end" ;;
  *) TIER="recommended" ;;
esac

echo
echo "Speech mode:"
echo "  1) ptt (push-to-talk)  [default]"
echo "  2) open_mic"
read -r -p "Choose speech mode [1-2]: " SPEECH_CHOICE
if [[ "${SPEECH_CHOICE:-1}" == "2" ]]; then
  SPEECH="open_mic"
else
  SPEECH="ptt"
fi

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/retroassist"
mkdir -p "$CONFIG_DIR"
CONFIG_PATH="$CONFIG_DIR/config.yaml"

if [[ ! -f "$CONFIG_PATH" && -f "$ROOT/config.example.yaml" ]]; then
  cp "$ROOT/config.example.yaml" "$CONFIG_PATH"
  echo "Wrote $CONFIG_PATH from config.example.yaml"
fi

echo
echo "Installing package (editable, with dev extras)..."
python3 -m pip install -e ".[dev]"

export RETROASSIST_MODEL_TIER="$TIER"
export RETROASSIST_SPEECH_MODE="$SPEECH"
echo
echo "Selected tier=$TIER speech=$SPEECH (exported for this shell session)."
echo "Edit $CONFIG_PATH to persist settings."
echo
echo "Next: ensure Ollama is installed and running, then:"
echo "  retroassist doctor"
echo "  retroassist serve"
echo
echo "Model pulls (examples; adjust to your tier):"
echo "  ollama pull qwen2.5vl:11b"
echo "  ollama pull qwen2.5:14b"
echo "  ollama pull nomic-embed-text"
