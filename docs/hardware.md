# Hardware Guidance

Hardware requirements for RetroAssist are summarized from the product specification ([ProjectSpec.md](ProjectSpec.md) §7).

| Tier | GPU VRAM | Example cards | Capability |
|------|----------|---------------|------------|
| Entry / usable | 12–16 GB | RTX 3060 12GB, 4060 Ti 16GB, used 3080 | Quantized / smaller models, usable frame analysis |
| Recommended | 24 GB | RTX 3090 / 4090, used workstation cards | Larger VLMs, smoother multi-image + longer context |
| High-end | 32 GB+ | RTX 5090 or multi-GPU | Maximum quality and future headroom |

**System:** 32 GB RAM minimum (64 GB preferred), modern multi-core CPU, fast NVMe storage, good USB bandwidth for cameras.

A GPU is **not** required to install the package or run the **mock / fixture** path (`doctor --skip-llm`, `test-visual --basic`, UI with mocked agents). Inference quality and latency scale with available hardware when using live Ollama models.

## Model defaults by tier

Default Ollama tags live in `src/retroassist/llm/models.py` and are selected via `models.tier` in config (or the interactive setup script). Override individual `models.llm` / `vision` / `embedding` names as needed. **Models are not bundled with the distribution.**

## Latency

On the recommended (~24 GB) tier, product targets are look-now &lt; 4–6 s and voice turnaround &lt; 2–3 s when possible. Mock/CI paths measure analyzer overhead only. See [installation.md](installation.md) (latency + degradation matrix) and [vertical-slice.md](vertical-slice.md).

## Setup

Full install, mock quickstart, Ollama pulls, and camera notes: [installation.md](installation.md). Live OBS Virtual Camera proxy: [live-proxy.md](live-proxy.md).
