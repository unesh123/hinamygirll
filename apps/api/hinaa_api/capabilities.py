from __future__ import annotations

import logging
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from .config import Settings

logger = logging.getLogger("hinaa.capabilities")


class ModelCapabilityRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    display_name: str
    provider: str
    kind: Literal["brain", "image", "voice", "research"]
    input_modalities: list[str] = Field(default_factory=list)
    output_modalities: list[str] = Field(default_factory=list)
    vision: bool = False
    document: bool = False
    image_generation: bool = False
    live: bool = False
    availability: Literal["healthy", "degraded", "unavailable"] = "healthy"
    description: str = ""
    availability_reason: str = ""


class CapabilitiesRegistry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    capabilities_version: str = "2026.1"
    models: list[ModelCapabilityRecord] = Field(default_factory=list)
    default_brain: str = "gemini-3.5-flash"
    default_image: str = "gemini-3.1-flash-image"
    default_voice: str = "gemini-live"


def build_capability_registry(settings: Settings) -> CapabilitiesRegistry:
    has_gemini = bool(settings.gemini_api_key and settings.gemini_api_key.get_secret_value())
    has_claude = bool(settings.claude_api_key and settings.claude_api_key.get_secret_value())
    has_openai = bool(settings.openai_api_key and settings.openai_api_key.get_secret_value())
    has_qwen = bool(settings.qwen_api_key and settings.qwen_api_key.get_secret_value())
    has_cx = settings.cx_gateway_configured
    has_agent_router = settings.agent_router_configured
    has_codecraft = settings.codecraft_configured

    models: list[ModelCapabilityRecord] = [
        # Brain Models
        ModelCapabilityRecord(
            id="gemini-3.5-flash",
            display_name="Gemini 3.5 Flash",
            provider="gemini",
            kind="brain",
            input_modalities=["text", "image", "document", "audio", "video"],
            output_modalities=["text"],
            vision=True,
            document=True,
            availability="healthy" if has_gemini else "unavailable",
            description="Configured multimodal reasoning model; live reachability is checked when invoked.",
        ),
        ModelCapabilityRecord(
            id="gemini-3.8-flash",
            display_name="Gemini 3.8 Flash",
            provider="gemini",
            kind="brain",
            input_modalities=["text", "image", "document", "audio"],
            output_modalities=["text"],
            vision=True,
            document=True,
            availability="healthy" if has_gemini else "unavailable",
            description="Configured multimodal reasoning model with vision and document input.",
        ),
        ModelCapabilityRecord(
            id="gemini-2.5-flash",
            display_name="Gemini 2.5 Flash",
            provider="gemini",
            kind="brain",
            input_modalities=["text", "image", "document"],
            output_modalities=["text"],
            vision=True,
            document=True,
            availability="healthy" if has_gemini else "unavailable",
            description="Multimodal fallback model for text, image, and document tasks.",
        ),
        ModelCapabilityRecord(
            id="claude-3-7-sonnet-20250219",
            display_name="Claude 3.7 Sonnet",
            provider="claude",
            kind="brain",
            input_modalities=["text", "image", "document"],
            output_modalities=["text"],
            vision=True,
            document=True,
            availability="healthy" if has_claude else "unavailable",
            description="Claude reasoning model with visual and document comprehension.",
        ),
        ModelCapabilityRecord(
            id="claude-3-5-haiku-20241022",
            display_name="Claude 3.5 Haiku",
            provider="claude",
            kind="brain",
            input_modalities=["text", "image"],
            output_modalities=["text"],
            vision=True,
            availability="healthy" if has_claude else "unavailable",
            description="Compact Claude model for responsive conversational turns.",
        ),
        ModelCapabilityRecord(
            id="qwen-max",
            display_name="Qwen Max",
            provider="qwen",
            kind="brain",
            input_modalities=["text"],
            output_modalities=["text"],
            availability="healthy" if has_qwen else "unavailable",
            description="Multilingual text synthesis model.",
        ),
        ModelCapabilityRecord(
            id=settings.cx_gateway_model,
            display_name="CX Gateway Brain",
            provider="cx-gateway",
            kind="brain",
            input_modalities=["text", "image", "document"],
            output_modalities=["text"],
            vision=True,
            document=True,
            availability="healthy" if has_cx else "unavailable",
            description="OpenAI-compatible gateway model with server-side routing.",
        ),
        ModelCapabilityRecord(
            id=settings.active_agent_router_model,
            display_name="Agent Router Brain",
            provider="agent-router",
            kind="brain",
            input_modalities=["text", "image", "document"],
            output_modalities=["text"],
            vision=True,
            document=True,
            availability="healthy" if has_agent_router else "unavailable",
            description="Fallback router for multi-provider conversations.",
        ),
        ModelCapabilityRecord(
            id="claude-fable-5",
            display_name="Claude Fable 5 (CodeCraft)",
            provider="codecraft",
            kind="brain",
            input_modalities=["text", "image", "document"],
            output_modalities=["text"],
            vision=True,
            document=True,
            availability="healthy" if has_codecraft else "unavailable",
            description="Frontier Claude Fable 5 model via CodeCraft with massive token budget.",
        ),
        ModelCapabilityRecord(
            id="claude-3-7-sonnet",
            display_name="Claude 3.7 Sonnet (CodeCraft)",
            provider="codecraft",
            kind="brain",
            input_modalities=["text", "image", "document"],
            output_modalities=["text"],
            vision=True,
            document=True,
            availability="healthy" if has_codecraft else "unavailable",
            description="Flagship hybrid reasoning model via CodeCraft.",
        ),
        ModelCapabilityRecord(
            id=settings.active_codecraft_model,
            display_name=f"CodeCraft Brain ({settings.active_codecraft_model})",
            provider="codecraft",
            kind="brain",
            input_modalities=["text", "image", "document"],
            output_modalities=["text"],
            vision=True,
            document=True,
            availability="healthy" if has_codecraft else "unavailable",
            description="CodeCraft API endpoint with multi-million token high-level reasoning.",
        ),
        ModelCapabilityRecord(
            id="gpt-4o",
            display_name="OpenAI GPT-4o",
            provider="openai",
            kind="brain",
            input_modalities=["text", "image"],
            output_modalities=["text"],
            vision=True,
            availability="healthy" if has_openai else "unavailable",
            description="OpenAI model for structured text and vision tasks.",
        ),
        ModelCapabilityRecord(
            id="mock",
            display_name="Mock Studio Brain",
            provider="mock",
            kind="brain",
            input_modalities=["text", "image"],
            output_modalities=["text"],
            vision=True,
            availability="healthy",
            description="Deterministic local sandbox for rapid testing.",
        ),

        # Image Generation Engines
        ModelCapabilityRecord(
            id="gemini-3.1-flash-image",
            display_name="Gemini 3.1 Flash Image",
            provider="gemini",
            kind="image",
            input_modalities=["text", "image"],
            output_modalities=["image"],
            image_generation=True,
            availability="healthy" if has_gemini else "unavailable",
            description="Gemini image generation endpoint; live availability is checked when invoked.",
        ),
        ModelCapabilityRecord(
            id="gemini-3-pro-image",
            display_name="Gemini 3 Pro Image",
            provider="gemini",
            kind="image",
            input_modalities=["text", "image"],
            output_modalities=["image"],
            image_generation=True,
            availability="healthy" if has_gemini else "unavailable",
            description="Gemini image generation endpoint with reference-image input.",
        ),
        ModelCapabilityRecord(
            id="comfyui",
            display_name="Local ComfyUI SDXL",
            provider="comfyui",
            kind="image",
            input_modalities=["text", "image"],
            output_modalities=["image"],
            image_generation=True,
            availability="degraded",
            description="Local node-based diffusion pipeline; the local service must be running.",
        ),
        ModelCapabilityRecord(
            id="magnific",
            display_name="Magnific Upscale & Relight",
            provider="magnific",
            kind="image",
            input_modalities=["image"],
            output_modalities=["image"],
            image_generation=True,
            availability="healthy" if bool(settings.magnific_api_key and settings.magnific_api_key.get_secret_value()) else "unavailable",
            description="Magnific upscaling and relighting endpoint.",
        ),

        # Voice & Speech Engines
        ModelCapabilityRecord(
            id="gemini-live",
            display_name="Gemini Live Voice",
            provider="gemini",
            kind="voice",
            input_modalities=["audio"],
            output_modalities=["audio"],
            live=True,
            availability="healthy" if has_gemini else "unavailable",
            description="Bidirectional Gemini voice streaming; microphone permission and provider reachability apply.",
        ),
        ModelCapabilityRecord(
            id="azure-speech",
            display_name="Azure Neural Speech",
            provider="azure",
            kind="voice",
            input_modalities=["audio"],
            output_modalities=["audio"],
            live=False,
            availability="healthy" if bool(settings.azure_speech_key and settings.azure_speech_key.get_secret_value()) else "unavailable",
            description="Azure multilingual neural TTS and STT.",
        ),
        ModelCapabilityRecord(
            id="browser-native",
            display_name="Browser Native Speech",
            provider="browser",
            kind="voice",
            input_modalities=["audio"],
            output_modalities=["audio"],
            live=False,
            availability="healthy",
            description="Browser SpeechSynthesis and Web Speech fallback; browser support and permissions apply.",
        ),
    ]

    # Keep the selector truthful when operators choose a model through
    # environment configuration. The curated records above describe common
    # models; these additions make every configured/allowed model discoverable
    # without inventing a successful live probe.
    known_ids = {model.id for model in models}

    def add_brain(model_id: str, provider: str, configured: bool, *, vision: bool = False) -> None:
        model_id = model_id.strip()
        if not model_id or model_id in known_ids:
            return
        models.append(
            ModelCapabilityRecord(
                id=model_id,
                display_name=model_id,
                provider=provider,
                kind="brain",
                input_modalities=["text", "image", "document"] if vision else ["text"],
                output_modalities=["text"],
                vision=vision,
                document=vision,
                availability="healthy" if configured else "unavailable",
                description="Configured model entry; live provider health is checked when invoked.",
                availability_reason=("Credentials configured" if configured else "Credentials not configured"),
            )
        )
        known_ids.add(model_id)

    for model_id in settings.gemini_allowed_models:
        add_brain(model_id, "gemini", has_gemini, vision=True)
    for model_id in settings.claude_allowed_models:
        add_brain(model_id, "claude", has_claude, vision=True)
    for model_id in settings.qwen_allowed_models:
        add_brain(model_id, "qwen", has_qwen)
    for model_id in settings.openai_allowed_models:
        add_brain(model_id, "openai", has_openai, vision=True)
    for model_id in settings.custom_allowed_models:
        add_brain(model_id, "custom", settings.custom_configured, vision=True)
    for model_id in settings.agent_router_allowed_models:
        add_brain(model_id, "agent-router", has_agent_router, vision=True)
    for model_id in settings.cx_allowed_models:
        add_brain(model_id, "cx-gateway", has_cx, vision=True)
    add_brain(settings.groq_model, "groq", settings.groq_configured)

    default_brain = "mock"
    if settings.provider_mode == "cx-gateway":
            default_brain = settings.cx_gateway_model
    elif settings.provider_mode == "agent-router":
        default_brain = settings.active_agent_router_model
    elif settings.provider_mode == "qwen":
        default_brain = settings.qwen_model
    elif settings.provider_mode == "openai":
        default_brain = settings.active_openai_model
    elif settings.provider_mode == "claude":
        default_brain = settings.active_claude_model
    elif settings.provider_mode in {"real", "gemini-live"}:
        # Historical ``real`` mode is Gemini brain + a voice provider.
        default_brain = settings.gemini_model
    elif settings.provider_mode in {"local", "mock"}:
        default_brain = "mock"
    elif settings.gemini_api_key and settings.gemini_api_key.get_secret_value():
        default_brain = settings.gemini_model

    return CapabilitiesRegistry(
        models=models,
        default_brain=default_brain,
        default_image="gemini-3.1-flash-image" if has_gemini else "comfyui",
        default_voice="gemini-live" if has_gemini else "browser-native",
    )
