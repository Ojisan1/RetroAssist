# Thin UI (Phase 7)

Local FastAPI + Jinja2/HTMX workbench served by `retroassist serve`.

## Run

```bash
pip install -e ".[dev]"
retroassist serve
# open http://127.0.0.1:8765
```

By default `ui.mock_agents: true` so serve works offline with mocked VLM/agent and fixture preview.

## Pages

| Path | Purpose |
|------|---------|
| `/` | Workbench: intake, look-now, ask, measurements, session transcript/suggestions, camera preview, export |
| `/knowledge` | File import + discovery candidates with **confirm before import** |
| `/settings` | Cameras, model tier, sampling FPS, **speech mode** (`ptt` / `open_mic`) |
| `/session/export` | Markdown download (+ save under sessions dir) |
| `/preview.jpg` | Low-rate camera/fixture thumbnail |
| `/health` | JSON health (includes `voice_status`) |

## Voice status

Header chip polls `/partials/voice-status`: `idle` | `listening` | `thinking` | `speaking`.

## Safety / KB policy

Discovery still never auto-ingests. Confirm is required. Empty KB remains empty-hit (no fabricated citations).

## Manual E2E

See [ui-e2e-checklist.md](ui-e2e-checklist.md).
