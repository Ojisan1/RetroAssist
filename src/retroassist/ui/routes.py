"""Thin FastAPI UI routes (server-rendered + HTMX)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Annotated, Any

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates

from retroassist.capture.base import encode_frame_jpeg
from retroassist.rag.discovery import DiscoveryCandidate, confirm_and_import, discover_candidates
from retroassist.ui.state import ServeState, frames_for_look, save_settings_overlay

PACKAGE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
UploadFileParam = Annotated[UploadFile, File()]

router = APIRouter(tags=["ui"])


def _state(request: Request) -> ServeState:
    return request.app.state.ui_state


def _ui_ctx(request: Request, **extra: Any) -> dict[str, Any]:
    state = _state(request)
    flash = state.clear_flash()
    cfg = state.config
    models = cfg.resolved_models()
    ui = cfg.raw.get("ui") or {}
    return {
        "request": request,
        "state": state,
        "flash": flash,
        "session": state.agent.session,
        "speech_mode": cfg.speech_mode,
        "model_tier": models["tier"],
        "models": models,
        "preview_interval_ms": int(ui.get("preview_interval_ms", 2000)),
        "kb_count": state.knowledge.count,
        "voice_status": state.voice_status,
        "candidates": state.discovery_candidates,
        **extra,
    }


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


@router.get("/", response_class=HTMLResponse)
async def workbench(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", _ui_ctx(request))


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "settings.html", _ui_ctx(request))


@router.get("/knowledge", response_class=HTMLResponse)
async def knowledge_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "knowledge.html", _ui_ctx(request))


@router.get("/partials/session", response_class=HTMLResponse)
async def session_partial(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "partials/session.html", _ui_ctx(request))


@router.get("/partials/voice-status", response_class=HTMLResponse)
async def voice_status_partial(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "partials/voice_status.html", _ui_ctx(request))


@router.get("/preview.jpg")
async def preview_jpeg(request: Request) -> Response:
    """Low-rate camera / fixture thumbnail."""
    state = _state(request)
    jpeg: bytes | None = None
    if state.cameras is not None:
        frames = state.cameras.read_all()
        if frames:
            encoded = encode_frame_jpeg(frames[0], quality=70)
            jpeg = encoded.data
    if jpeg is None and state.fixture_image and state.fixture_image.is_file():
        image = cv2.imread(str(state.fixture_image), cv2.IMREAD_COLOR)
        if image is not None:
            h, w = image.shape[:2]
            scale = min(1.0, 480 / max(h, w))
            if scale < 1.0:
                image = cv2.resize(image, (int(w * scale), int(h * scale)))
            ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if ok:
                jpeg = bytes(buf)
    if jpeg is None:
        blank = np.full((120, 160, 3), 40, dtype=np.uint8)
        ok, buf = cv2.imencode(".jpg", blank, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        jpeg = bytes(buf) if ok else b""
    return Response(content=jpeg, media_type="image/jpeg")


@router.post("/session/intake")
async def session_intake(
    request: Request,
    symptom: str = Form(...),
    notes: str = Form(""),
) -> RedirectResponse:
    state = _state(request)
    state.set_voice("thinking")
    await state.agent.intake(symptom, notes)
    state.note(f"Intake: {symptom}")
    state.set_voice("idle")
    state.flash = "Intake recorded."
    return _redirect("/")


@router.post("/session/look-now")
async def session_look_now(request: Request) -> RedirectResponse:
    state = _state(request)
    state.set_voice("thinking")
    frames = frames_for_look(state)
    if not frames:
        state.flash = "No camera or fixture frames available for look-now."
        state.set_voice("idle")
        return _redirect("/")
    obs = await state.agent.look_now(frames)
    state.note(f"Look now: {obs.get('summary', '')[:160]}")
    state.set_voice("idle")
    state.flash = "Look-now complete."
    return _redirect("/")


@router.post("/session/ask")
async def session_ask(request: Request, query: str = Form(...)) -> RedirectResponse:
    state = _state(request)
    state.set_voice("listening")
    state.note(f"You: {query}")
    state.set_voice("thinking")
    suggestion = await state.agent.ask(query)
    spoken = str(suggestion.get("action") or "")
    state.set_voice("speaking")
    state.note(f"Assist: {spoken[:240]}")
    state.set_voice("idle")
    state.flash = "Suggestion ready."
    return _redirect("/")


@router.post("/session/measure")
async def session_measure(request: Request, text: str = Form(...)) -> RedirectResponse:
    state = _state(request)
    state.set_voice("thinking")
    suggestion = await state.agent.report_measurement(text)
    state.note(f"Measurement: {text}")
    state.note(f"Assist: {str(suggestion.get('action') or '')[:240]}")
    state.set_voice("idle")
    state.flash = "Measurement recorded."
    return _redirect("/")


@router.get("/session/export")
async def session_export(request: Request) -> Response:
    """Download current session as markdown (also saved under sessions/)."""
    state = _state(request)
    md = state.agent.export_markdown()
    sessions = state.config.resolve_data_path("sessions")
    sessions.mkdir(parents=True, exist_ok=True)
    path = sessions / f"ui-{state.agent.session.session_id[:8]}.md"
    path.write_text(md, encoding="utf-8")
    return StreamingResponse(
        io.BytesIO(md.encode("utf-8")),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@router.post("/settings")
async def save_settings(
    request: Request,
    speech_mode: str = Form("ptt"),
    model_tier: str = Form("recommended"),
    continuous_fps: float = Form(0.4),
    active_fps: float = Form(1.0),
    mock_agents: str | None = Form(None),
    camera_device: str = Form(""),
    camera_role: str = Form("overview"),
) -> RedirectResponse:
    state = _state(request)
    mode = speech_mode.strip().lower()
    if mode not in ("ptt", "open_mic"):
        state.flash = "Invalid speech mode."
        return _redirect("/settings")
    overlay: dict[str, Any] = {
        "speech": {"mode": mode},
        "models": {"tier": model_tier},
        "sampling": {
            "continuous_fps": float(continuous_fps),
            "active_fps": float(active_fps),
        },
        "ui": {"mock_agents": mock_agents in {"on", "true", "1", "yes"}},
    }
    device = camera_device.strip()
    if device:
        try:
            device_val: int | str = int(device)
        except ValueError:
            device_val = device
        overlay["cameras"] = {
            "sources": [{"id": "overview", "device": device_val, "role": camera_role}],
        }
    path = save_settings_overlay(state.config, overlay)
    state.flash = f"Settings saved to {path}"
    return _redirect("/settings")


@router.post("/knowledge/import")
async def knowledge_import(
    request: Request,
    file: UploadFileParam,
) -> RedirectResponse:
    state = _state(request)
    if not file.filename:
        state.flash = "No file selected."
        return _redirect("/knowledge")
    dest_dir = state.config.resolve_data_path("knowledge_base") / "imports"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(file.filename).name
    data = await file.read()
    dest.write_bytes(data)
    count = await state.knowledge.ingest(str(dest), metadata={"platform": "import"})
    state.flash = f"Imported {dest.name}: {count} chunk(s). KB size={state.knowledge.count}"
    return _redirect("/knowledge")


@router.post("/knowledge/discover")
async def knowledge_discover(
    request: Request,
    platform: str = Form(...),
) -> RedirectResponse:
    state = _state(request)

    async def _offline_search(query: str, limit: int) -> list[DiscoveryCandidate]:
        return [
            DiscoveryCandidate(
                title=f"Synthetic notes for {query}",
                source_url="https://example.invalid/synthetic_psu_notes.md",
                reason="Offline UI seed (confirm required before import)",
                domain="example.invalid",
                score=1.0,
            )
        ][:limit]

    state.discovery_candidates = await discover_candidates(
        platform,
        limit=5,
        search_fn=_offline_search if state.mock else None,
    )
    state.flash = (
        f"Found {len(state.discovery_candidates)} candidate(s). "
        "Confirm import explicitly — nothing was ingested yet."
    )
    return _redirect("/knowledge")


@router.post("/knowledge/confirm")
async def knowledge_confirm(
    request: Request,
    index: int = Form(...),
) -> RedirectResponse:
    state = _state(request)
    if index < 0 or index >= len(state.discovery_candidates):
        state.flash = "Invalid candidate index."
        return _redirect("/knowledge")
    candidate = state.discovery_candidates[index]
    if state.mock or "example.invalid" in candidate.source_url:
        from retroassist.paths import samples_knowledge_root

        sample = samples_knowledge_root() / "synthetic_psu_notes.md"
        if sample.is_file():
            n = await state.knowledge.ingest(
                str(sample),
                metadata={
                    "platform": "confirmed",
                    "discovered_from": candidate.source_url,
                },
            )
            state.flash = (
                f"Confirmed import of local sample for {candidate.title!r}: {n} chunk(s)."
            )
        else:
            state.flash = "Confirm failed: sample knowledge file missing."
        return _redirect("/knowledge")

    dest = state.config.resolve_data_path("knowledge_base") / "discovered"
    dest.mkdir(parents=True, exist_ok=True)
    n = await confirm_and_import(candidate, state.knowledge.store, dest_dir=dest)
    state.flash = f"Confirmed import: {n} chunk(s) from {candidate.source_url}"
    return _redirect("/knowledge")
