# RetroAssist

Local-first, open-source workbench assistant for skilled electronics technicians working on classic/vintage hardware they have limited prior experience with.

RetroAssist combines live visual observation of the workbench (cameras / OBS Virtual Camera), retrieval of schematics and service documentation, and multimodal LLMs to suggest logical next diagnostic steps—primarily via hands-free voice interaction.

**Status:** Pre-alpha. The repository is being scaffolded; application features are not yet implemented.

## Disclaimer

RetroAssist is an experimental open-source tool provided **as-is with no warranty**.

It can produce incorrect, incomplete, or outdated suggestions.  
You remain fully responsible for all actions taken while using it.

Never rely solely on this tool for high-voltage work, CRT service, or any procedure that could cause injury, fire, or further damage to equipment. Always cross-check critical steps against primary documentation and your own judgment.

See [docs/safety.md](docs/safety.md) for the full safety and responsibility statement.

## Goals

- Help competent technicians take on unfamiliar classic platforms with greater confidence
- Support restoration and practical longevity/mod work
- Stay fully local and open-source (MIT)
- Remain useful even with an incomplete or empty knowledge base

## Non-goals

- Fully autonomous repair
- Replacement for fundamental electronics skill or safety practices
- Serving complete beginners
- Commercial / SaaS product
- Guaranteed correct diagnosis (the human remains responsible)

## Hardware guidance

| Tier | GPU VRAM | Capability |
|------|----------|------------|
| Entry / usable | 12–16 GB | Quantized models, frame/clip analysis |
| Recommended | 24 GB | Larger VLMs, smoother multi-image + longer context |
| High-end | 32 GB+ | Maximum quality and future headroom |

System: 32 GB RAM minimum (64 GB preferred), modern multi-core CPU, fast NVMe, good USB bandwidth for cameras. A GPU is not required merely to install the package; model quality scales with hardware.

## License

MIT — see [LICENSE](LICENSE).

## Documentation

- [Product specification](docs/ProjectSpec.md)
- [Testing strategy](docs/testing-strategy.md)
- [Safety and responsibility](docs/safety.md)
- [Hardware](docs/hardware.md)
- [Installation](docs/installation.md)
- [Architecture](docs/architecture.md)
- [Session export](docs/session-export.md)

## Private test fixtures

Do **not** commit copyrighted manuals or YouTube-derived frames. Real private keyframes belong only under `tests/fixtures/private/` (gitignored). Public fixtures must be synthetic, public-domain, or clearly licensed.

## Development (scaffold)

```bash
pip install -e ".[dev]"
ruff check .
pytest
```
