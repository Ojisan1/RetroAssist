"""FastAPI application factory (thin scaffold for later UI routes)."""

from __future__ import annotations

from fastapi import FastAPI

from retroassist import __version__
from retroassist.config import AppConfig, load_config


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Build the RetroAssist API app."""
    cfg = config or load_config()
    app = FastAPI(
        title="RetroAssist",
        version=__version__,
        description="Local-first classic electronics repair assistant (pre-alpha).",
    )
    app.state.config = cfg

    @app.get("/health")
    async def health() -> dict[str, object]:
        models = cfg.resolved_models()
        return {
            "status": "ok",
            "version": __version__,
            "model_tier": models["tier"],
            "speech_mode": cfg.speech_mode,
        }

    return app
