#!/usr/bin/env bash
# RetroAssist interactive setup (Phase 8)
# Models are not bundled — optional ollama pull commands are printed at the end.

set -euo pipefail

echo "RetroAssist setup"
echo "================="

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
echo "Hardware tier (default model names; see docs/hardware.md):"
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

echo
echo "Install profile:"
echo "  1) base          — runtime only (end-user default)"
echo "  2) base+speech   — optional faster-whisper + mic support"
echo "  3) dev           — base + pytest/ruff (contributors)"
read -r -p "Choose profile [1-3]: " PROFILE_CHOICE
EXTRAS=""
WITH_SPEECH=0
case "${PROFILE_CHOICE:-1}" in
  2) EXTRAS="speech"; WITH_SPEECH=1 ;;
  3) EXTRAS="dev"; WITH_SPEECH=0 ;;
  *) EXTRAS=""; WITH_SPEECH=0 ;;
esac

WHISPER="base"
STT_PROVIDER="mock"
if [[ "$WITH_SPEECH" == "1" ]]; then
  echo
  echo "Whisper model size (downloaded on first live STT use):"
  echo "  1) tiny"
  echo "  2) base  [default]"
  echo "  3) small"
  read -r -p "Choose Whisper size [1-3]: " W_CHOICE
  case "${W_CHOICE:-2}" in
    1) WHISPER="tiny" ;;
    3) WHISPER="small" ;;
    *) WHISPER="base" ;;
  esac
  read -r -p "Set speech.stt_provider=whisper now? [y/N]: " USE_LIVE
  if [[ "${USE_LIVE:-}" =~ ^[Yy]$ ]]; then
    STT_PROVIDER="whisper"
  fi
fi

echo
read -r -p "Print ollama pull commands for this tier? [Y/n]: " PULL_MODELS
DO_PULL_HINTS=1
if [[ "${PULL_MODELS:-}" =~ ^[Nn]$ ]]; then
  DO_PULL_HINTS=0
fi

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/retroassist"
mkdir -p "$CONFIG_DIR"
CONFIG_PATH="$CONFIG_DIR/config.yaml"

if [[ ! -f "$CONFIG_PATH" && -f "$ROOT/config.example.yaml" ]]; then
  cp "$ROOT/config.example.yaml" "$CONFIG_PATH"
  echo "Wrote $CONFIG_PATH from config.example.yaml"
fi

echo
if [[ -n "$EXTRAS" ]]; then
  echo "Installing package (editable, extras=[$EXTRAS])..."
  python3 -m pip install -e ".[${EXTRAS}]"
else
  echo "Installing package (editable, base)..."
  python3 -m pip install -e .
fi

echo
echo "Persisting tier/speech settings to $CONFIG_PATH ..."
python3 - "$CONFIG_PATH" "$TIER" "$SPEECH" "$WHISPER" "$STT_PROVIDER" <<'PY'
from pathlib import Path
import sys
from retroassist.config import apply_setup_overrides

path, tier, speech, whisper, stt = sys.argv[1:6]
apply_setup_overrides(
    Path(path),
    tier=tier,
    speech_mode=speech,
    whisper_model=whisper,
    stt_provider=stt,
)
print("Updated config overrides.")
PY

export RETROASSIST_MODEL_TIER="$TIER"
export RETROASSIST_SPEECH_MODE="$SPEECH"

echo
echo "Ensuring data directories..."
python3 -c "from retroassist.doctor import ensure_platform_dirs; print('\\n'.join(str(p) for p in ensure_platform_dirs()))"

PROFILE_LABEL="${EXTRAS:-base}"
echo
echo "Selected: tier=$TIER speech=$SPEECH profile=$PROFILE_LABEL stt=$STT_PROVIDER whisper=$WHISPER"
echo
echo "Next steps:"
echo "  # Offline / no GPU — mock path (always works after install):"
echo "  retroassist doctor --skip-llm"
echo "  retroassist test-visual --basic"
echo "  retroassist serve"
echo
echo "  # Live models (optional; install Ollama separately):"
echo "  retroassist doctor"
echo
echo "See docs/installation.md for the full quickstart and degradation matrix."

if [[ "$DO_PULL_HINTS" == "1" ]]; then
  echo
  echo "Suggested model pulls for tier=$TIER (not run automatically; models are not bundled):"
  python3 -c "from retroassist.llm.models import get_profile; p = get_profile('$TIER'); print(f'  ollama pull {p.vision}'); print(f'  ollama pull {p.llm}'); print(f'  ollama pull {p.embedding}')"
fi
