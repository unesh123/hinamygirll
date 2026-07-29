from __future__ import annotations

from contextlib import asynccontextmanager
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from . import __version__
from .audio import validate_wav
from .config import Settings, get_settings
from .errors import HinaaError, hinaa_error_handler, unhandled_error_handler
from .models import ProviderStatus, SpeechRequest, TranscriptResponse, TurnRequest
from .services import ConversationService


def _correlation_id(value: str | None) -> str:
    try:
        return str(UUID(value)) if value else str(uuid4())
    except ValueError:
        return str(uuid4())


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    service = ConversationService(active_settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
        yield

    app = FastAPI(
        title="HINAA API",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.service = service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Correlation-ID"],
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

    @app.get("/health/ready")
    async def readiness() -> JSONResponse:
        missing = active_settings.missing_real_configuration()
        ready = active_settings.provider_mode == "mock" or not missing
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ok" if ready else "degraded",
                "mode": active_settings.provider_mode,
                "missingConfiguration": missing if not ready else [],
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
                id="azure-speech",
                capabilities=["stt", "tts", "ne-NP", "pcm-wav"],
                state="healthy" if active_settings.azure_configured else "unavailable",
                userMessage=(
                    "Backend configuration is present; no live call has been made."
                    if active_settings.azure_configured
                    else "Backend credentials are not configured."
                ),
            ),
            ProviderStatus(
                id="gemini",
                capabilities=["llm", "structured-turn-plan", "text-stream"],
                state="healthy" if active_settings.gemini_configured else "unavailable",
                userMessage=(
                    "Backend configuration is present; no live call has been made."
                    if active_settings.gemini_configured
                    else "Backend credentials are not configured."
                ),
            ),
        ]

    @app.post("/v1/speech/transcriptions", response_model=TranscriptResponse)
    async def transcribe(
        audio: UploadFile = File(...),
        language: str = Form("ne-NP"),
        provider_mode: str = Form("mock"),
    ) -> TranscriptResponse:
        if provider_mode not in {"mock", "real"}:
            raise HinaaError("PROVIDER_MODE_INVALID", "Choose mock or real mode.", 422, False, True)
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

    @app.post("/v1/conversations/turns:stream")
    async def stream_turn(request: Request, body: TurnRequest) -> StreamingResponse:
        async def guarded_stream():  # type: ignore[no-untyped-def]
            try:
                async for event in service.stream_turn(body, request.state.correlation_id):
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
        return Response(
            result.value,
            media_type="audio/wav",
            headers={
                "X-HINAA-Provider": result.provider,
                "X-HINAA-Latency-Ms": str(result.latency_ms),
                "X-HINAA-Total-Ms": str(int((perf_counter() - started) * 1000)),
                "Content-Disposition": 'inline; filename="hinaa-turn.wav"',
            },
        )

    return app


app = create_app()
