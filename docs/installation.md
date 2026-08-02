# Installation

Installation instructions will be expanded in later phases (interactive setup scripts, model download, camera configuration).

## Current scaffold (developers)

Requires Python 3.11+.

```bash
pip install -e ".[dev]"
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv sync --extra dev
```

Verify:

```bash
retroassist
pytest
```

Windows and Linux are both intended targets; Windows is the primary end-user platform.
