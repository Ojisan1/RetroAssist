"""Thin local web UI for RetroAssist."""

from retroassist.ui.routes import router
from retroassist.ui.state import ServeState, build_serve_state

__all__ = ["ServeState", "build_serve_state", "router"]
