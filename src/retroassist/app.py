"""FastAPI application factory with thin UI routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from retroassist import __version__
from retroassist.config import AppConfig, load_config


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Build the RetroAssist API + thin UI app."""
    cfg = config or load_config()
    static_dir = Path(__file__).resolve().parent / "ui" / "static"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from retroassist.ui.state import build_serve_state

        app.state.ui_state = await build_serve_state(cfg)
        try:
            yield
        finally:
            state = getattr(app.state, "ui_state", None)
            if state is not None and state.cameras is not None:
                try:
                    state.cameras.close()
                except Exception:  # noqa: BLE001
                    pass

    app = FastAPI(
        title="RetroAssist",
        version=__version__,
        description="Local-first classic electronics repair assistant (pre-alpha).",
        lifespan=lifespan,
    )
    app.state.config = cfg

    @app.get("/health")
    async def health() -> dict[str, object]:
        models = cfg.resolved_models()
        ui_state = getattr(app.state, "ui_state", None)
        return {
            "status": "ok",
            "version": __version__,
            "model_tier": models["tier"],
            "speech_mode": cfg.speech_mode,
            "voice_status": getattr(ui_state, "voice_status", "idle"),
            "mock_ui": bool(getattr(ui_state, "mock", True)),
        }

    from retroassist.ui.routes import router as ui_router

    app.include_router(ui_router)
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app
