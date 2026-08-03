# Live Proxy Testing (Manual)

RetroAssist treats **OBS Virtual Camera** as a normal capture device (OpenCV index or friendly name). No OBS WebSocket control in v1.

Use this workflow for exploratory testing with real repair footage when physical hardware is unavailable.

## Workflow

1. Play a high-quality classic electronics repair video (YouTube or local file).
2. In OBS Studio:
   - Add a **Window Capture** / **Browser** / **Media Source** of the video.
   - Start **Virtual Camera** (Controls → Start Virtual Camera).
3. Confirm the device appears in RetroAssist:
   ```bash
   retroassist doctor --skip-llm
   ```
   Look for `capture.devices` entries such as `OBS Virtual Camera` (name listing is best-effort; an index like `1:Camera 1` is enough).
4. Point RetroAssist at that device in config (`%APPDATA%/RetroAssist/config.yaml` or project `config.yaml`):

```yaml
cameras:
  sources:
    - id: overview
      device: "OBS Virtual Camera"   # or a numeric index from doctor
      role: overview
```

5. Interact with text queries that match what is on screen (voice arrives in Phase 6).

## What this validates

- Continuous / active sampling and on-demand **look now**
- Latency of the capture → encode path
- How well later vision/agent loops track a long repair session

This path is **manual / exploratory**, not CI. Automated tests use fixture images under `tests/fixtures/images/` instead.

## Zero-camera / fixture mode

With `cameras.sources: []`, RetroAssist runs in zero-camera mode. Headless tests inject frames via `MultiCameraManager.fixture_mode(...)` or `FixtureCaptureSource`.
