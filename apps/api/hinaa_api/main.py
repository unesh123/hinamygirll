from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from . import __version__
from .audio import validate_wav
from .config import Settings, get_settings
from .errors import HinaaError, hinaa_error_handler, unhandled_error_handler
from .models import ProviderStatus, SpeechRequest, ToolRequest, TranscriptResponse, TurnRequest, VoiceProfile
from .persistence import MemoryService, init_db
from .persistence.auth import AuthContext, auth_dependency_factory, resolve_auth
from .persistence.db import reset_session_factory
from .prompts import PROMPT_VERSION
from .realtime import RealtimeGateway
from .services import ConversationService
from .tools import registry
from .vmc_bridge import vmc_bridge
from .voice_profiles import public_profiles


logger = logging.getLogger(__name__)


class RememberBody(BaseModel):
    content: Annotated[str, Field(min_length=1, max_length=500)]
    category: Annotated[str, Field(default="other", max_length=40)] = "other"
    sourceTurnRef: str | None = None


class MemoryToggleBody(BaseModel):
    enabled: bool


def _correlation_id(value: str | None) -> str:
    try:
        return str(UUID(value)) if value else str(uuid4())
    except ValueError:
        return str(uuid4())


def create_app(settings: Settings | None = None) -> FastAPI:
    # Without this, INFO-level breadcrumbs (realtime message trace) and even
    # uncaught-exception logging were effectively invisible: Python's root
    # logger has no handler by default, and the previous bare `except
    # Exception:` in the realtime turn loop did not log at all. This is why
    # turn failures looked like an unexplained "connection lost" with zero
    # server-side trace to diagnose from.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    active_settings = settings or get_settings()
    reset_session_factory()
    memory_service = (
        MemoryService(init_db(active_settings)) if active_settings.persistence_enabled else None
    )
    service = ConversationService(active_settings, memory_service=memory_service)
    realtime = RealtimeGateway(active_settings, service)
    require_auth = (
        auth_dependency_factory(active_settings, memory_service)
        if memory_service is not None
        else None
    )

    def _resolve_user_id(request: Request) -> str | None:
        """Best-effort user identity for durable memory.

        When persistence is disabled (or auth cannot be resolved) the turn
        still works — it simply has no durable memory attached.
        """
        if memory_service is None:
            return None
        try:
            auth = resolve_auth(
                request,
                active_settings,
                memory_service,
                authorization=request.headers.get("Authorization"),
                x_hinaa_dev_user=request.headers.get("X-HINAA-Dev-User"),
            )
        except HinaaError:
            return None
        return auth.user_id

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
        # Start VMC UDP listener for VSeeFace face tracking
        await vmc_bridge.start_udp(port=39539)
        yield
        vmc_bridge.stop()

    app = FastAPI(
        title="HINAA API",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.service = service
    app.state.memory_service = memory_service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "X-Correlation-ID", "Authorization", "X-HINAA-Dev-User"],
        expose_headers=["X-Correlation-ID", "X-HINAA-Provider", "X-HINAA-Latency-Ms"],
    )
    app.add_exception_handler(HinaaError, hinaa_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        correlation_id = _correlation_id(request.headers.get("X-Correlation-ID"))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "ok", "service": "hinaa-api", "version": __version__}

    @app.websocket("/ws/vmc")
    async def vmc_websocket(ws: WebSocket) -> None:
        """WebSocket endpoint — streams VSeeFace face tracking data to frontend.

        VSeeFace → UDP 39539 → vmc_bridge → this WS → frontend AvatarPresence
        """
        await vmc_bridge.add_client(ws)
        try:
            while True:
                # Keep connection alive; bridge pushes data on UDP receipt
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            vmc_bridge.remove_client(ws)

    @app.get("/health/ready")
    async def readiness() -> JSONResponse:
        if active_settings.provider_mode == "openai":
            missing = active_settings.missing_openai_voice_configuration()
        elif active_settings.provider_mode == "custom":
            missing = active_settings.missing_custom_voice_configuration()
        elif active_settings.provider_mode == "agent-router":
            missing = active_settings.missing_agent_router_voice_configuration()
        elif active_settings.provider_mode == "real":
            missing = active_settings.missing_real_configuration()
        else:
            missing = []
        ready = not missing
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ok" if ready else "degraded",
                "mode": active_settings.provider_mode,
                "missingConfiguration": missing if not ready else [],
                "persistenceEnabled": active_settings.persistence_enabled,
                "authMode": active_settings.auth_mode,
                "promptVersion": PROMPT_VERSION,
            },
        )

    @app.get("/v1/providers", response_model=list[ProviderStatus])
    async def provider_status() -> list[ProviderStatus]:
        return [
            ProviderStatus(
                id="mock",
                capabilities=["stt", "llm", "tts", "ne-NP", "offline"],
                state="healthy",
                userMessage="Deterministic local mock is ready.",
            ),
            ProviderStatus(
                id="local",
                capabilities=[
                    "llm",
                    "zero-credit",
                    "offline",
                    "stt" if active_settings.local_stt_configured else "stt-unconfigured",
                    "tts" if active_settings.local_tts_configured else "tts-placeholder",
                ],
                state="healthy" if active_settings.local_stt_configured else "degraded",
                userMessage=(
                    "Zero-credit local text brain, STT command and TTS command are ready."
                    if active_settings.local_stt_configured and active_settings.local_tts_configured
                    else "Zero-credit local text brain and fast placeholder voice are ready; "
                    "configure local STT/TTS commands for fully local microphone speech."
                ),
            ),
            ProviderStatus(
                id="groq",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "official",
                    "stt:azure-speech"
                    if active_settings.azure_configured
                    else "stt-local-required",
                    "tts:azure-speech"
                    if active_settings.azure_configured
                    else "tts-placeholder",
                ],
                state="healthy" if active_settings.groq_configured else "unavailable",
                userMessage=(
                    "Backend Groq configuration is present; Microsoft Speech will handle voice."
                    if active_settings.groq_configured and active_settings.azure_configured
                    else "Backend Groq configuration is present; no live call has been made."
                    if active_settings.groq_configured
                    else "Groq API key is not configured in the backend."
                ),
            ),
            ProviderStatus(
                id="openai",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "official",
                    f"default-model:{active_settings.active_openai_model}",
                    *[f"model:{model}" for model in active_settings.openai_allowed_models],
                ],
                state="healthy" if active_settings.openai_configured else "unavailable",
                userMessage=(
                    "Backend OpenAI configuration is present; no live call has been made. "
                    f"Key source: {active_settings.active_openai_key_label}."
                    if active_settings.openai_configured
                    else "OpenAI API key is not configured in the backend."
                ),
            ),
            ProviderStatus(
                id="custom",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.active_custom_model}",
                    *[f"model:{model}" for model in active_settings.custom_allowed_models],
                ],
                state="healthy" if active_settings.custom_configured else "unavailable",
                userMessage=(
                    "Custom model gateway configuration is present; no live call has been made."
                    if active_settings.custom_configured
                    else (
                        "Custom model gateway needs OPENAI_CODEX_API_KEY "
                        "and OPENAI_CODEX_BASE_URL."
                    )
                ),
            ),
            ProviderStatus(
                id="agent-router",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.active_agent_router_model}",
                    *[f"model:{model}" for model in active_settings.agent_router_allowed_models],
                ],
                state="healthy" if active_settings.agent_router_configured else "unavailable",
                userMessage=(
                    "Agent router configuration is present; no live call has been made."
                    if active_settings.agent_router_configured
                    else (
                        "Agent router needs AGENT_ROUTER_API_KEY."
                    )
                ),
            ),
            ProviderStatus(
                id="cx-gateway",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.cx_gateway_model}",
                    *[f"model:{model}" for model in active_settings.cx_allowed_models],
                ],
                state="healthy" if active_settings.cx_gateway_configured else "unavailable",
                userMessage=(
                    "CX Gateway (cx/gpt-5.6-sol) is configured and ready."
                    if active_settings.cx_gateway_configured
                    else "CX Gateway needs CX_GATEWAY_API_KEY and CX_GATEWAY_BASE_URL."
                ),
            ),
            ProviderStatus(
                id="gemini-live",
                capabilities=[
                    "llm",
                    "s2s",
                    "native-bidi-audio",
                    "pcm-24khz",
                    "barge-in-native",
                    "default-model:gemini-2.5-flash",
                ],
                state="healthy" if active_settings.gemini_configured else "unavailable",
                userMessage=(
                    "Gemini Live Bidi S2S (sub-300ms native multimodal audio) is ready."
                    if active_settings.gemini_configured
                    else "GEMINI_API_KEY is not configured in backend."
                ),
            ),

            ProviderStatus(
                id="azure-speech",
                capabilities=["stt", "tts", "ne-NP", "pcm-wav"],
                state="disabled",
                userMessage="Azure subscription is disabled. ElevenLabs and local providers are used.",
            ),
            ProviderStatus(
                id="elevenlabs",
                capabilities=["tts", "stt", "scribe-v2", "multilingual", "mp3-streaming"],
                state="healthy" if active_settings.elevenlabs_configured else "unavailable",
                userMessage=(
                    "ElevenLabs TTS and Scribe v2 STT configured server-side."
                    if active_settings.elevenlabs_configured
                    else "ELEVENLABS_API_KEY is not configured in backend."
                ),
            ),
            ProviderStatus(
                id="gemini",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    f"default-model:{active_settings.gemini_model}",
                    *[f"model:{model}" for model in active_settings.gemini_allowed_models],
                ],
                state="healthy" if active_settings.gemini_configured else "unavailable",
                userMessage=(
                    "Backend configuration is present; no live call has been made."
                    if active_settings.gemini_configured
                    else "Backend credentials are not configured."
                ),
            ),
            ProviderStatus(
                id="deepgram",
                capabilities=["tts", "stt", "aura-2-odysseus-en", "flux-general-en"],
                state="healthy" if active_settings.deepgram_configured else "unavailable",
                userMessage=(
                    "Deepgram TTS and STT configured server-side for Hiro."
                    if active_settings.deepgram_configured
                    else "Deepgram_API_KEY is not configured in backend."
                ),
            ),
        ]

    @app.get("/v1/voice-profiles", response_model=list[VoiceProfile])
    async def voice_profiles() -> list[VoiceProfile]:
        return public_profiles(
            active_settings.azure_speech_female_voice,
            active_settings.azure_speech_male_voice,
        )

    @app.websocket("/v1/realtime")
    async def realtime_session(websocket: WebSocket) -> None:
        await realtime.handle(websocket, user_id=_resolve_user_id(websocket))

    @app.post("/v1/speech/transcriptions", response_model=TranscriptResponse)
    async def transcribe(
        audio: UploadFile = File(...),
        language: str = Form("ne-NP"),
        provider_mode: str = Form("mock"),
    ) -> TranscriptResponse:
        if provider_mode not in {"mock", "local", "groq", "openai", "custom", "real"}:
            raise HinaaError(
                "PROVIDER_MODE_INVALID",
                "Choose mock, local, groq, openai, custom or real mode.",
                422,
                False,
                True,
            )
        if audio.content_type not in {"audio/wav", "audio/wave", "audio/x-wav"}:
            raise HinaaError("AUDIO_FORMAT_UNSUPPORTED", "Upload PCM WAV audio.", 415, False, True)
        data = await audio.read(active_settings.max_audio_bytes + 1)
        await audio.close()
        if len(data) > active_settings.max_audio_bytes:
            raise HinaaError("AUDIO_SIZE_EXCEEDED", "The recording is too large.", 413, False, True)
        pcm = validate_wav(data, max_seconds=active_settings.max_audio_seconds)
        result = await service.transcribe(pcm, language, provider_mode)
        return TranscriptResponse(
            text=result.value,
            language=language,
            provider=result.provider,
            latencyMs=result.latency_ms,
        )

    @app.post("/v1/tools/approve")
    async def approve_tool(request: Request) -> dict[str, Any]:
        data = await request.json()
        approval_id = data.get("approval_id")
        approved = data.get("approved", False)
        
        from hinaa_api.tools.browser_agent import approval_events
        if approval_id in approval_events:
            approval_events[approval_id]["approved"] = approved
            approval_events[approval_id]["event"].set()
            return {"status": "success"}
        return {"status": "error", "error": "Approval ID not found"}

    @app.get("/v1/tools/poll")
    async def poll_tool(job_id: str) -> dict[str, Any]:
        from hinaa_api.persistence.db import get_session_factory
        from hinaa_api.persistence.orm import GenerationSet, ImageJob
        from hinaa_api.config import get_settings
        settings = get_settings()
        
        session_factory = get_session_factory(settings)
        with session_factory() as session:
            gen_set = session.query(GenerationSet).filter_by(id=job_id).first()
            if not gen_set:
                raise HTTPException(status_code=404, detail="Job not found")
                
            jobs = session.query(ImageJob).filter_by(generation_set_id=job_id).all()
            if not jobs:
                return {"id": job_id, "status": "processing", "images": [], "total": 0}
                
            status = "success"
            errors = []
            images = []
            for j in jobs:
                if j.status in ["failed", "cancelled"]:
                    errors.append(f"Image {j.id} failed")
                    if status != "processing":
                        status = "error"
                elif j.status == "pending" or j.status == "processing":
                    status = "processing"
                
                if j.status == "completed" and j.file_path:
                    # Return the safe image URL endpoint
                    images.append(f"http://127.0.0.1:8000/v1/generated-images/{j.id}")
                    
            if status == "error" and len(images) > 0:
                # Partial success
                status = "success"
                
            return {
                "id": job_id,
                "status": status,
                "images": images,
                "total": len(jobs),
                "error": " | ".join(errors) if errors else None
            }

    @app.get("/v1/generated-images/{image_id}")
    async def get_generated_image(image_id: str):
        from hinaa_api.persistence.db import get_session_factory
        from hinaa_api.persistence.orm import ImageJob
        from hinaa_api.config import get_settings
        settings = get_settings()
        from fastapi.responses import FileResponse
        import os
        from pathlib import Path
        
        session_factory = get_session_factory(settings)
        with session_factory() as session:
            job = session.query(ImageJob).filter_by(id=image_id).first()
            if not job or not job.file_path:
                raise HTTPException(status_code=404, detail="Image not found")
                
            file_path = Path(job.file_path)
            
            # Security checks
            allowed_root = Path("apps/api/data/images").resolve()
            try:
                resolved_path = file_path.resolve()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid path")
                
            if not resolved_path.is_relative_to(allowed_root):
                raise HTTPException(status_code=403, detail="Forbidden path traversal")
                
            if not resolved_path.exists() or not resolved_path.is_file():
                raise HTTPException(status_code=404, detail="File missing on disk")
                
            ext = resolved_path.suffix.lower()
            if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
                raise HTTPException(status_code=415, detail="Unsupported media type")
                
            content_type = "image/png"
            if ext in [".jpg", ".jpeg"]:
                content_type = "image/jpeg"
            elif ext == ".webp":
                content_type = "image/webp"
                
            return FileResponse(resolved_path, media_type=content_type)

    @app.post("/v1/tools/execute")
    async def execute_tool(request: Request, body: ToolRequest) -> dict[str, Any]:
        tool_def = registry.get_tool(body.toolName)
        if not tool_def:
            raise HTTPException(status_code=404, detail="Tool not found")
        if tool_def.requires_confirmation and not body.confirmed:
            raise HinaaError(
                "TOOL_CONFIRMATION_REQUIRED",
                f"Confirm the {tool_def.display_name} action before HINAA runs it.",
                409,
                False,
                True,
            )

        handler = registry._handlers.get(body.toolName)
        if not handler:
            raise HTTPException(status_code=500, detail="Tool handler not registered")
            
        try:
            import inspect
            from pydantic import BaseModel
            
            sig = inspect.signature(handler)
            parsed_params = body.parameters.copy()
            
            user_id = body.userId or _resolve_user_id(request)
            if user_id:
                parsed_params.setdefault("userId", user_id)
            if "conversationId" not in parsed_params:
                conv_id = body.conversationId or request.headers.get("X-Conversation-ID")
                if conv_id:
                    parsed_params["conversationId"] = conv_id

                    
            if sig.parameters:
                first_param = list(sig.parameters.values())[0]
                param_type = first_param.annotation
                if inspect.isclass(param_type) and issubclass(param_type, BaseModel):
                    parsed_params = param_type(**parsed_params)
                    
            import time
            import uuid
            
            started_at = int(time.time() * 1000)
            result = await handler(parsed_params)
            completed_at = int(time.time() * 1000)
            
            # If the handler returned a REQUIRES_APPROVAL string
            if isinstance(result, str) and result.startswith("REQUIRES_APPROVAL:"):
                parts = result.split(":", 2)
                if len(parts) == 3:
                    action, args = parts[1], parts[2]
                    return {
                        "status": "RequiresApproval",
                        "data": {
                            "action": action,
                            "args": args
                        }
                    }

            # If the handler already returned a StandardToolResultEnvelope-like dict, use it directly
            if isinstance(result, dict) and "status" in result and ("data" in result or "images" in result or "job_id" in result):
                return result

            envelope = {
                "id": str(uuid.uuid4()),
                "toolId": body.toolName,
                "status": "success",
                "startedAt": started_at,
                "completedAt": completed_at,
                "data": result,
            }
            return {"status": "success", "data": envelope}
        except HinaaError:
            raise
        except Exception:
            logger.exception("Tool execution failed: %s", body.toolName)
            raise HinaaError(
                "TOOL_EXECUTION_FAILED",
                "HINAA could not complete that action. Please try again.",
                502,
                True,
                False,
            ) from None

    @app.post("/v1/conversations/turns:stream")
    async def stream_turn(request: Request, body: TurnRequest) -> StreamingResponse:
        user_id = _resolve_user_id(request)

        async def guarded_stream():  # type: ignore[no-untyped-def]
            try:
                async for event in service.stream_turn(
                    body, request.state.correlation_id, user_id=user_id
                ):
                    yield event
            except HinaaError as error:
                yield service._event(
                    "error",
                    {
                        "code": error.code,
                        "message": error.message,
                        "retryable": error.retryable,
                        "correlationId": request.state.correlation_id,
                    },
                )

        return StreamingResponse(guarded_stream(), media_type="application/x-ndjson")

    @app.delete("/v1/sessions/{session_id}", status_code=204)
    async def clear_session(session_id: str) -> Response:
        service.memory.clear(session_id)
        return Response(status_code=204)

    @app.post("/v1/speech/synthesis")
    async def synthesize(body: SpeechRequest) -> Response:
        started = perf_counter()
        result = await service.synthesize(body)
        media_type = "audio/mpeg" if result.provider == "elevenlabs" else "audio/wav"
        return Response(
            result.value,
            media_type=media_type,
            headers={
                "X-HINAA-Provider": result.provider,
                "X-HINAA-Latency-Ms": str(result.latency_ms),
                "X-HINAA-Total-Ms": str(int((perf_counter() - started) * 1000)),
                "Content-Disposition": 'inline; filename="hinaa-turn.wav"',
            },
        )

    if memory_service is not None and require_auth is not None:

        @app.get("/v1/privacy/status")
        async def privacy_status(auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
            return memory_service.privacy_status(auth.user_id)

        @app.patch("/v1/privacy/memory")
        async def toggle_memory(
            body: MemoryToggleBody, auth: AuthContext = Depends(require_auth)
        ) -> dict[str, object]:
            return memory_service.set_memory_enabled(auth.user_id, body.enabled)

        @app.get("/v1/privacy/memories")
        async def list_memories(auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
            return {"memories": memory_service.list_memories(auth.user_id)}

        @app.post("/v1/privacy/memories")
        async def remember(
            body: RememberBody, auth: AuthContext = Depends(require_auth)
        ) -> dict[str, object]:
            return memory_service.remember(
                auth.user_id,
                body.content,
                category=body.category,
                source_turn_ref=body.sourceTurnRef,
                explicit=True,
            )

        @app.delete("/v1/privacy/memories/{memory_id}")
        async def forget_memory(
            memory_id: str, auth: AuthContext = Depends(require_auth)
        ) -> dict[str, object]:
            return memory_service.forget(auth.user_id, memory_id)

        @app.delete("/v1/privacy/conversations/{conversation_id}")
        async def clear_conversation(
            conversation_id: str, auth: AuthContext = Depends(require_auth)
        ) -> dict[str, object]:
            return memory_service.clear_conversation(auth.user_id, conversation_id)

        @app.get("/v1/privacy/export")
        async def export_data(auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
            return memory_service.export_data(auth.user_id)

        @app.delete("/v1/privacy/account")
        async def delete_all(auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
            return memory_service.delete_all(auth.user_id)

    return app


app = create_app()
