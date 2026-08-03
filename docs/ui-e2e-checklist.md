# UI E2E checklist (Phase 7)

Manual workshop checks. CI covers mocked smoke only.

## Prep

- [ ] `pip install -e ".[dev]"`
- [ ] `retroassist serve` starts without error
- [ ] Browser opens `http://127.0.0.1:8765`

## Fixture / mock path (required)

- [ ] Workbench shows fixture or placeholder preview
- [ ] Intake → Look now → Ask produces suggestion text in session panel
- [ ] Export session downloads markdown with intake/observations/suggestions
- [ ] Knowledge discover lists candidates without ingesting
- [ ] Confirm import increases chunk count (or imports sample in mock mode)
- [ ] Settings: change speech mode to `open_mic`, save, reload shows new mode
- [ ] Voice status chip updates through idle/thinking during ask

## Virtual camera (optional)

- [ ] OBS Virtual Camera listed / set in Settings camera device
- [ ] Preview updates with live scene at low rate
- [ ] Look now uses camera still when fixture not forced

## Voice (optional, Phase 6)

- [ ] With live speech extras installed, status chip can show listening/speaking during listen workflows (CLI remains primary for full STT/TTS)
