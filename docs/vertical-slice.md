# Vertical Slice Gate (Phase 5.5)

Hard gate before Phase 6 (speech) and Phase 7 (UI polish). Proves the **text-only** path:

```
Keyframe / camera still
  → Vision analysis
  → RAG retrieval
  → Grounded next-step suggestions
  → Session export (markdown)
```

Canonical criteria: [execution-plan.md](execution-plan.md) §6.

## Checklist

| Criterion | Status (mocked CI path) |
|-----------|-------------------------|
| Basic suite headless: **PS-01, METER-01, EMPTY-01, NO-KB-01** | Pass via `retroassist test-visual --basic` |
| Text intake (typed symptom + notes) | `retroassist session intake` / `session run` |
| Look-now from fixture frame | `session look-now --image …` / `session run --case` |
| Sample KB → suggestions can cite retrieval | PS-01 assertions |
| Empty KB → no fabricated manual page citations | NO-KB-01 assertions |
| Safety language on mains/HV-adjacent (PS-01) | Pass |
| Markdown export: intake, observations, suggestions, timestamps, latency | Pass |
| Look-now latency measured & logged | Present on observation + `## Latency notes` (mock path is sub-ms; live target &lt; 4–6s on recommended hardware) |
| Minimal CLI sufficient for the slice | `session` + `test-visual` (no Phase 7 UI required) |

**Go/no-go:** Phase 6/7 must not start until this checklist is green on the mocked path. Optional live Ollama / OBS Virtual Camera smoke remains operator-local (`--no-mock`, [live-proxy.md](live-proxy.md)).

## Commands

```bash
# Gate suite (mocked VLM + MockAgentLLM)
retroassist test-visual --basic
python tools/run_visual_suite.py --basic
# Full Phase 5 suite
retroassist test-visual --all

# One-shot text slice using a query fixture
retroassist session run --case ps01 --out session.md --mock

# Stepwise
retroassist session intake --symptom "No power" --notes "PSU on bench" --mock --kb-sample synthetic_psu_notes.md
retroassist session look-now --image tests/fixtures/images/power_supply/sample.png --mock --vision-case power_supply
retroassist session next --query "What first?" --mock --agent-case ps01
retroassist session export --out session.md
```

## Latency notes

- **Mock / CI:** look-now latency reflects analyzer overhead only (typically well under 1 s). Logged for regression wiring, not as a hardware SLA.
- **Live (recommended ~24 GB VRAM tier):** product target for look-now remains **&lt; 4–6 seconds**; compare against `latency.look_now_target_seconds` in config. Record actuals in exported session `## Latency notes` when validating on hardware.

## Manual smoke (optional)

1. Fixture path (required for gate): `session run --case ps01 --out smoke.md --mock`
2. OBS Virtual Camera (optional): capture a still or configure a camera source, then `session look-now --image … --no-mock` with Ollama running
