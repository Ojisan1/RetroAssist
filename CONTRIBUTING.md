# Contributing to RetroAssist

Thanks for interest in improving RetroAssist. This project is MIT-licensed and local-first.

## Development setup

```bash
git clone https://github.com/Ojisan1/RetroAssist.git
cd RetroAssist
pip install -e ".[dev]"
# optional live speech: pip install -e ".[dev,speech]"
```

Or run `scripts/setup.ps1` / `scripts/setup.sh` and choose the **dev** profile.

## Checks before opening a PR

```bash
ruff check .
pytest
retroassist doctor --skip-llm
retroassist test-visual --basic
```

## Guidelines

- Prefer small, focused changes that match existing module boundaries (`capture`, `vision`, `rag`, `agent`, `speech`, `ui`).
- Do **not** commit copyrighted manuals or YouTube-derived frames. Private keyframes belong only under `tests/fixtures/private/` (gitignored). Public fixtures must be synthetic, public-domain, or clearly licensed.
- Keep discovery confirm-only; never silent-scrape or auto-ingest into the knowledge base.
- Mock paths should remain the default for CI; live Ollama / speech extras stay optional.
- See [docs/testing-strategy.md](docs/testing-strategy.md), [docs/safety.md](docs/safety.md), and [docs/execution-plan.md](docs/execution-plan.md).

## Code of conduct expectations

Be respectful in issues and PRs. Domain experts evaluating repair suggestions are especially welcome — honest feedback is valued.
