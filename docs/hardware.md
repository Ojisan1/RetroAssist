# Hardware Guidance

Hardware requirements for RetroAssist are summarized from the product specification.

| Tier | GPU VRAM | Example cards | Capability |
|------|----------|---------------|------------|
| Entry / usable | 12–16 GB | RTX 3060 12GB, 4060 Ti 16GB, used 3080 | Quantized models, frame/clip analysis |
| Recommended | 24 GB | RTX 3090 / 4090, used workstation cards | Larger VLMs, smoother multi-image + longer context |
| High-end | 32 GB+ | RTX 5090 or multi-GPU | Maximum quality and future headroom |

**System:** 32 GB RAM minimum (64 GB preferred), modern multi-core CPU, fast NVMe storage, good USB bandwidth for cameras.

A GPU is not required to install the package. Inference quality and latency scale with available hardware. Detailed setup steps will land in later phases.
