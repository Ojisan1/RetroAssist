# Draft interactive setup for RetroAssist (Phase 1)
# Full installer polish lands in Phase 8.

$ErrorActionPreference = "Stop"

Write-Host "RetroAssist setup (draft)"
Write-Host "========================="

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
Write-Host "Hardware tier (affects default model names):"
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

# Patch tier / speech if PyYAML is available after install; otherwise remind user.
Write-Host ""
Write-Host "Installing package (editable, with dev extras)..."
& python -m pip install -e ".[dev]"

$env:RETROASSIST_MODEL_TIER = $tier
$env:RETROASSIST_SPEECH_MODE = $speech
Write-Host ""
Write-Host "Selected tier=$tier speech=$speech (exported for this shell session)."
Write-Host "Edit $configPath to persist settings."
Write-Host ""
Write-Host "Next: ensure Ollama is installed and running, then:"
Write-Host "  retroassist doctor"
Write-Host "  retroassist serve"
Write-Host ""
Write-Host "Model pulls (examples; adjust to your tier):"
Write-Host "  ollama pull qwen2.5vl:11b"
Write-Host "  ollama pull qwen2.5:14b"
Write-Host "  ollama pull nomic-embed-text"
