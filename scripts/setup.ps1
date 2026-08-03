# RetroAssist interactive setup (Phase 8)
# Models are not bundled — optional ollama pull commands are printed at the end.

$ErrorActionPreference = "Stop"

Write-Host "RetroAssist setup"
Write-Host "================="

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Error "Python was not found on PATH. Install Python 3.11+ and re-run."
}

$ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Detected Python $ver"
& python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python 3.11+ is required."
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "Hardware tier (default model names; see docs/hardware.md):"
Write-Host "  1) entry       (12-16 GB VRAM)"
Write-Host "  2) recommended (24 GB VRAM)  [default]"
Write-Host "  3) high_end    (32 GB+ VRAM)"
$tierChoice = Read-Host "Choose tier [1-3]"
switch ($tierChoice) {
    "1" { $tier = "entry" }
    "3" { $tier = "high_end" }
    Default { $tier = "recommended" }
}

Write-Host ""
Write-Host "Speech mode:"
Write-Host "  1) ptt (push-to-talk)  [default]"
Write-Host "  2) open_mic"
$speechChoice = Read-Host "Choose speech mode [1-2]"
$speech = if ($speechChoice -eq "2") { "open_mic" } else { "ptt" }

Write-Host ""
Write-Host "Install profile:"
Write-Host "  1) base          — runtime only (end-user default)"
Write-Host "  2) base+speech   — optional faster-whisper + mic support"
Write-Host "  3) dev           — base + pytest/ruff (contributors)"
$profileChoice = Read-Host "Choose profile [1-3]"
switch ($profileChoice) {
    "2" { $extras = "speech"; $withSpeech = $true }
    "3" { $extras = "dev"; $withSpeech = $false }
    Default { $extras = ""; $withSpeech = $false }
}

$whisper = "base"
$sttProvider = "mock"
if ($withSpeech) {
    Write-Host ""
    Write-Host "Whisper model size (downloaded on first live STT use):"
    Write-Host "  1) tiny"
    Write-Host "  2) base  [default]"
    Write-Host "  3) small"
    $wChoice = Read-Host "Choose Whisper size [1-3]"
    switch ($wChoice) {
        "1" { $whisper = "tiny" }
        "3" { $whisper = "small" }
        Default { $whisper = "base" }
    }
    $useLive = Read-Host "Set speech.stt_provider=whisper now? [y/N]"
    if ($useLive -match '^[Yy]') {
        $sttProvider = "whisper"
    }
}

Write-Host ""
$pullModels = Read-Host "Print ollama pull commands for this tier? [Y/n]"
$doPullHints = -not ($pullModels -match '^[Nn]')

$configDir = Join-Path $env:APPDATA "RetroAssist"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
$configPath = Join-Path $configDir "config.yaml"

if (-not (Test-Path $configPath)) {
    $example = Join-Path $root "config.example.yaml"
    if (Test-Path $example) {
        Copy-Item $example $configPath
        Write-Host "Wrote $configPath from config.example.yaml"
    }
}

Write-Host ""
if ($extras) {
    Write-Host "Installing package (editable, extras=[$extras])..."
    & python -m pip install -e ".[$extras]"
} else {
    Write-Host "Installing package (editable, base)..."
    & python -m pip install -e .
}

Write-Host ""
Write-Host "Persisting tier/speech settings to $configPath ..."
& python -c @"
from pathlib import Path
from retroassist.config import apply_setup_overrides
apply_setup_overrides(
    Path(r'$configPath'),
    tier='$tier',
    speech_mode='$speech',
    whisper_model='$whisper',
    stt_provider='$sttProvider',
)
print('Updated config overrides.')
"@

$env:RETROASSIST_MODEL_TIER = $tier
$env:RETROASSIST_SPEECH_MODE = $speech

Write-Host ""
Write-Host "Ensuring data directories..."
& python -c "from retroassist.doctor import ensure_platform_dirs; print('\n'.join(str(p) for p in ensure_platform_dirs()))"

Write-Host ""
Write-Host "Selected: tier=$tier speech=$speech profile=$(if ($extras) { $extras } else { 'base' }) stt=$sttProvider whisper=$whisper"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  # Offline / no GPU — mock path (always works after install):"
Write-Host "  retroassist doctor --skip-llm"
Write-Host "  retroassist test-visual --basic"
Write-Host "  retroassist serve"
Write-Host ""
Write-Host "  # Live models (optional; install Ollama separately):"
Write-Host "  retroassist doctor"
Write-Host ""
Write-Host "See docs/installation.md for the full quickstart and degradation matrix."

if ($doPullHints) {
    Write-Host ""
    Write-Host "Suggested model pulls for tier=$tier (not run automatically; models are not bundled):"
    & python -c @"
from retroassist.llm.models import get_profile
p = get_profile('$tier')
print(f'  ollama pull {p.vision}')
print(f'  ollama pull {p.llm}')
print(f'  ollama pull {p.embedding}')
"@
}
