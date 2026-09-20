from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env.local"
# Anchored to this file, not the working directory: the API is launched from
# apps/api, so CWD-relative "apps/api/data" paths resolve to a stray
# apps/api/apps/api/data tree and split writes away from reads.
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_LOCAL_DATABASE_URL = f"sqlite+pysqlite:///{Path.home() / '.hinaa' / 'hinaa.db'}"

# Official Anthropic defaults remain the safe default. The documented mwapi
# gateway publishes a different catalog; aliases preserve stale local browser
# preferences during the transition instead of sending unsupported model IDs.
OFFICIAL_CLAUDE_DEFAULT_MODELS = (
    "claude-sonnet-4-20250514,claude-opus-4-20250514,claude-3-5-haiku-20241022"
)
MWAPI_CLAUDE_DEFAULT_MODELS = (
    "claude-sonnet-4-6,claude-opus-4-6,claude-haiku-4-5-20251001,claude-opus-5,claude-sonnet-5,claude-opus-4-8,claude-opus-4-7"
)
MWAPI_CLAUDE_MODEL_ALIASES = {
    "claude-sonnet-4-20250514": "claude-sonnet-4-6",
    "claude-opus-4-20250514": "claude-opus-4-6",
    "claude-3-5-haiku-20241022": "claude-haiku-4-5-20251001",
    "claude-haiku": "claude-haiku-4-5-20251001",
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
    "claude-sonnet": "claude-sonnet-4-6",
    "claude-opus": "claude-opus-4-6",
    "claude-3-5-sonnet": "claude-sonnet-4-6",
    "claude-3-7-sonnet": "claude-sonnet-5",
    "claude-3-opus": "claude-opus-4-6",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        populate_by_name=True,
    )

    provider_mode: Literal["mock", "local", "groq", "openai", "custom", "real", "claude", "qwen", "agent-router", "cx-gateway", "gemini-live", "codecraft"] = Field(
        "claude", alias="HINAA_PROVIDER_MODE"
    )
    azure_speech_key: SecretStr | None = Field(None, alias="AZURE_SPEECH_KEY")
    azure_speech_region: str | None = Field(None, alias="AZURE_SPEECH_REGION")
    gemini_api_key: SecretStr | None = Field(None, alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-3.5-flash-lite", alias="GEMINI_MODEL")
    gemini_planner_model: str = Field("gemini-3.5-flash-lite", alias="GEMINI_PLANNER_MODEL")
    gemini_allowed_models_raw: str = Field(
        (
            "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.6-flash,"
            "gemini-3.8-flash,gemini-3.5-flash,gemini-3-flash-preview,"
            "gemini-flash-latest,gemini-flash-lite-latest,gemini-pro-latest"
        ),
        alias="GEMINI_ALLOWED_MODELS",
    )
    # Claude is an explicit HINAA provider. It accepts a standard Anthropic key
    # via ANTHROPIC_API_KEY for convenience, but never reuses ANTHROPIC_AUTH_TOKEN
    # because that token may belong to a separate Claude Code gateway/account.
    claude_api_key: SecretStr | None = Field(
        None,
        validation_alias=AliasChoices("HINAA_CLAUDE_API_KEY", "ANTHROPIC_API_KEY"),
    )
    claude_base_url: str = Field("https://api.anthropic.com", alias="HINAA_CLAUDE_BASE_URL")
    # auto uses the evidenced Claude-compatible Bearer route for mwapi.dev;
    # choose anthropic or openai-compatible explicitly to override.
    claude_protocol: Literal["auto", "anthropic", "openai-compatible"] = Field("auto", alias="HINAA_CLAUDE_PROTOCOL")
    claude_model: str = Field("claude-sonnet-4-20250514", alias="HINAA_CLAUDE_MODEL")
    claude_allowed_models_raw: str = Field(
        OFFICIAL_CLAUDE_DEFAULT_MODELS,
        alias="HINAA_CLAUDE_ALLOWED_MODELS",
    )
    # QwenCloud supports the OpenAI-compatible Chat Completions contract. The
    # primary key name is HINAA_QWEN_API_KEY; QWEN_API_KEY and DASHSCOPE_API_KEY
    # remain accepted for the official dashboard and SDK environment examples.
    qwen_api_key: SecretStr | None = Field(
        None,
        validation_alias=AliasChoices("HINAA_QWEN_API_KEY", "QWEN_API_KEY", "DASHSCOPE_API_KEY"),
    )
    qwen_base_url: str = Field(
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        alias="HINAA_QWEN_BASE_URL",
    )
    qwen_model: str = Field("qwen3.7-plus", alias="HINAA_QWEN_MODEL")
    qwen_allowed_models_raw: str = Field(
        "qwen3.7-plus,qwen3.7-max,qwen3.5-flash,qwen3.6-plus",
        alias="HINAA_QWEN_ALLOWED_MODELS",
    )
    # Local ComfyUI remains private to this machine. Submitting multiple jobs
    # fills its queue promptly; GPU execution concurrency stays conservative by
    # default to avoid OOM on consumer cards such as an 8 GB RTX 4060.
    vmc_port: int = Field(39539, alias="HINAA_VMC_PORT")
    comfyui_base_url: str = Field("http://127.0.0.1:8188", alias="HINAA_COMFYUI_BASE_URL")
    comfyui_max_concurrent_jobs: int = Field(1, ge=1, le=4, alias="HINAA_COMFYUI_MAX_CONCURRENT_JOBS")
    groq_api_key: SecretStr | None = Field(None, alias="GROQ_API_KEY")
    groq_model: str = Field("llama-3.1-8b-instant", alias="GROQ_MODEL")
    openai_api_key: SecretStr | None = Field(None, alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-5-mini", alias="OPENAI_MODEL")
    # Fast brain for casual chat: reasoning models (cx/gpt-5.6-sol, agent
    # router) burn hidden tokens before the first visible one, which makes
    # small talk feel slow. Short social turns route to this non-reasoning
    # model when an OpenAI key is present; deep work keeps the reasoning brain.
    openai_fast_model: str = Field("gpt-5-mini", alias="HINAA_OPENAI_FAST_MODEL")
    openai_codex_api_key: SecretStr | None = Field(None, alias="OPENAI_CODEX_API_KEY")
    openai_codex_model: str = Field("gpt-5-mini", alias="OPENAI_CODEX_MODEL")
    openai_codex_base_url: str | None = Field(
        "https://growing-large-edges-airfare.trycloudflare.com/v1",
        alias="OPENAI_CODEX_BASE_URL",
    )
    openai_codex_allowed_models_raw: str = Field(
        (
            "auto,cx/gpt-5.6-sol,DeepSeek-V4-Flash,DeepSeek-V4-Pro,glm-5.1,glm-5.2,"
            "kat-coder-pro-v2.5,Kimi-K2.6,MiniMax-M3,Qwen3.5-397B-A17B,"
            "Qwen3.6-35B-A3B,sensenova-6.7-flash-lite,sensenova-u1-fast,"
            "step-3.5-flash,step-3.5-flash-2603,step-3.7-flash,step-router-v1,"
            "stepaudio-2.5-asr,stepaudio-2.5-chat,stepaudio-2.5-realtime,"
            "stepaudio-2.5-tts"
        ),
        alias="OPENAI_CODEX_ALLOWED_MODELS",
    )
    openai_key_source: Literal["auto", "primary", "codex"] = Field(
        "auto", alias="HINAA_OPENAI_KEY_SOURCE"
    )
    openai_allowed_models_raw: str = Field(
        "gpt-5-mini,gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol,gpt-5.4-mini,gpt-5.4-nano",
        alias="HINAA_OPENAI_ALLOWED_MODELS",
    )
    # CX Gateway — separate provider for cx/gpt-5.6-sol and similar models
    # Set CX_GATEWAY_API_KEY + CX_GATEWAY_BASE_URL to enable.
    cx_gateway_api_key: SecretStr | None = Field(None, alias="CX_GATEWAY_API_KEY")
    cx_gateway_base_url: str | None = Field(None, alias="CX_GATEWAY_BASE_URL")
    cx_gateway_model: str = Field("cx/gpt-5.6-sol", alias="CX_GATEWAY_MODEL")
    cx_gateway_allowed_models_raw: str = Field(
        "cx/gpt-5.6-sol",
        alias="CX_GATEWAY_ALLOWED_MODELS",
    )
    agent_router_api_key: SecretStr | None = Field(
        None,
        validation_alias=AliasChoices(
            "AGENT_ROUTER_API_KEY",
            "ROUTER_BYNARA_API_KEY",
            "ROUTER_BYNARA_AOI_kEY",
            "BYNARA_API_KEY",
        ),
    )
    agent_router_model: str = Field(
        "agnes-2.5-flash",
        validation_alias=AliasChoices("AGENT_ROUTER_MODEL", "ROUTER_BYNARA_MODEL", "BYNARA_MODEL"),
    )
    agent_router_base_url: str | None = Field(
        None,
        validation_alias=AliasChoices(
            "AGENT_ROUTER_BASE_URL",
            "ROUTER_BYNARA_BASE_URL",
            "BYNARA_BASE_URL",
        ),
    )
    agent_router_allowed_models_raw: str = Field(
        (
            "agnes-2.5-flash,nemotron-3.5-lightning-free,laguna-s-2.1,ling-3.0-flash-fin-free,stepfun-3.7-flash,"
            "deepseek-v4-flash,deepseek-v4-pro,deepseek-v4.1-flash,deepseek-v4-flash-alibaba,deepseek-v4-pro-alibaba,deepseek-v4-flash-vision-exp,"
            "claude-sonnet-5,claude-opus-4.7,claude-opus-4.7-promo,claude-opus-4.8,claude-opus-5,claude-opus-5-promo,claude-fable-5,claude-fable-5.1,"
            "gpt-5.5,gpt-5.6-luna,gpt-5.6-sol,gpt-5.6-terra,gpt-6-astra,grok-4.6,kimi-k2.7-code,kimi-k3,minimax-m3,"
            "qwen3.7-flash,qwen3.8-flash,qwen3.8-max,qwen3.8-27b,qwen3.8-2.4t,qwen3.8-max-alibaba,"
            "glm-5.2,glm-5.3,glm-5.3-flash,gemini-3.8-flash-high,mimo-v2.5,mimo-v2.5-pro,muse-spark-1.2,muse-spark-1.3,tencent-hy4-preview"
        ),
        validation_alias=AliasChoices(
            "AGENT_ROUTER_ALLOWED_MODELS",
            "ROUTER_BYNARA_ALLOWED_MODELS",
            "BYNARA_ALLOWED_MODELS",
        ),
    )
    # CodeCraft API — 100M+ tokens, Claude Fable 5, and frontier models via codecraftapi.com
    codecraft_api_key: SecretStr | None = Field(
        None,
        validation_alias=AliasChoices(
            "CODE_CRAFT_API_KEY",
            "CODE_CRAFTAI_API_KEY",
            "CODECRAFT_API_KEY",
        ),
    )
    codecraft_base_url: str | None = Field(
        "https://codecraftapi.com/v1",
        validation_alias=AliasChoices(
            "CODE_CRAFT_BASE_URL",
            "CODE_CRAFTAI_BASE_URL",
            "CODECRAFT_BASE_URL",
        ),
    )
    codecraft_model: str = Field(
        "claude-fable-5",
        validation_alias=AliasChoices("CODE_CRAFT_MODEL", "CODE_CRAFTAI_MODEL", "CODECRAFT_MODEL"),
    )
    codecraft_allowed_models_raw: str = Field(
        (
            "claude-fable-5,claude-fable-5.1,claude-sonnet-5,claude-opus-5,"
            "claude-3-7-sonnet,claude-3-5-sonnet,gpt-5.6-sol,gpt-6-astra,"
            "gpt-5.5,gpt-4o,deepseek-chat,deepseek-v4-pro,deepseek-v4-flash,"
            "kimi-k3,qwen3.8-max,glm-5.3"
        ),
        validation_alias=AliasChoices(
            "CODE_CRAFT_ALLOWED_MODELS",
            "CODE_CRAFTAI_ALLOWED_MODELS",
            "CODECRAFT_ALLOWED_MODELS",
        ),
    )
    # Ollama Local Engine — fast, uncensored, zero-credit offline brain
    ollama_base_url: str = Field(
        "http://localhost:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "HINAA_OLLAMA_BASE_URL"),
    )
    ollama_model: str = Field(
        "dolphin-mistral:7b",
        validation_alias=AliasChoices("OLLAMA_MODEL", "HINAA_OLLAMA_MODEL"),
    )
    ollama_allowed_models_raw: str = Field(
        "*",
        validation_alias=AliasChoices("OLLAMA_ALLOWED_MODELS", "HINAA_OLLAMA_ALLOWED_MODELS"),
    )
    ollama_timeout_seconds: float = Field(
        120.0,
        validation_alias=AliasChoices("OLLAMA_TIMEOUT_SECONDS", "HINAA_OLLAMA_TIMEOUT_SECONDS"),
    )
    # You.com — private, server-side real-time web intelligence. Keep the key
    # in apps/api/.env.local as YDC_API_KEY; never expose it to Vite/browser code.
    youcom_api_key: SecretStr | None = Field(None, alias="YDC_API_KEY")
    youcom_base_url: str = Field("https://api.you.com", alias="YOUCOM_BASE_URL")
    youcom_contents_base_url: str = Field("https://ydc-index.io", alias="YOUCOM_CONTENTS_BASE_URL")
    youcom_timeout_seconds: float = Field(30.0, alias="YOUCOM_TIMEOUT_SECONDS")
    # Magnific / Freepik — cloud image generation (HINAA's image brain).
    # Contract: docs.magnific.com — x-magnific-api-key header, async task
    # pattern on every route (POST → task_id → poll GET {path}/{task_id}).
    magnific_api_key: SecretStr | None = Field(None, alias="MAGNIFIC_API_KEY")
    freepik_api_key: SecretStr | None = Field(None, alias="FREEPIK_API_KEY")
    magnific_base_url: str = Field("https://api.magnific.com", alias="MAGNIFIC_BASE_URL")
    magnific_timeout_seconds: float = Field(240.0, alias="MAGNIFIC_TIMEOUT_SECONDS")
    magnific_poll_seconds: float = Field(2.0, alias="MAGNIFIC_POLL_SECONDS")
    magnific_t2i_path: str = Field("/v1/ai/text-to-image/{model}", alias="MAGNIFIC_T2I_PATH")
    magnific_reference_path: str = Field("/v1/ai/text-to-image/flux-kontext-pro", alias="MAGNIFIC_REFERENCE_PATH")
    magnific_upscale_path: str = Field("/v1/ai/image-upscaler", alias="MAGNIFIC_UPSCALE_PATH")
    magnific_model_fast: str = Field("flux-2-turbo", alias="MAGNIFIC_MODEL_FAST")
    magnific_model_quality: str = Field("flux-dev", alias="MAGNIFIC_MODEL_QUALITY")
    magnific_reference_strength: float = Field(0.7, alias="MAGNIFIC_REFERENCE_STRENGTH")
    magnific_upscale_default: bool = Field(False, alias="MAGNIFIC_UPSCALE_DEFAULT")

    azure_speech_female_voice: str = Field("hi-IN-SwaraNeural", alias="AZURE_SPEECH_FEMALE_VOICE")
    azure_speech_male_voice: str = Field("hi-IN-MadhurNeural", alias="AZURE_SPEECH_MALE_VOICE")
    elevenlabs_api_key: SecretStr | None = Field(None, alias="ELEVENLABS_API_KEY")
    elevenlabs_base_url: str = Field("https://api.elevenlabs.io", alias="ELEVENLABS_BASE_URL")
    elevenlabs_voice_id: str = Field("TRnaQb7q41oL7sV0w6Bu", alias="ELEVENLABS_VOICE_ID")
    elevenlabs_hinaa_voice_id: str = Field("TRnaQb7q41oL7sV0w6Bu", alias="ELEVENLABS_HINAA_VOICE_ID")
    elevenlabs_hiro_voice_id: str = Field("ErXwobaYiN019PkySvjV", alias="ELEVENLABS_HIRO_VOICE_ID")
    elevenlabs_model_id: str = Field("eleven_multilingual_v2", alias="ELEVENLABS_MODEL_ID")
    elevenlabs_stt_model_id: str = Field("scribe_v2", alias="ELEVENLABS_STT_MODEL_ID")
    elevenlabs_tts_model_fast: str = Field("eleven_flash_v2_5", alias="ELEVENLABS_TTS_MODEL_FAST")
    elevenlabs_tts_model_expressive: str = Field("eleven_multilingual_v2", alias="ELEVENLABS_TTS_MODEL_EXPRESSIVE")
    elevenlabs_output_format: str = Field("mp3_44100_128", alias="ELEVENLABS_OUTPUT_FORMAT")
    elevenlabs_language_policy: str = Field("auto", alias="ELEVENLABS_LANGUAGE_POLICY")
    # Fish Audio — server-side multilingual TTS with Nepali/English
    # switching. The key is read from FISH_AUDIO_API_KEY or the legacy
    # Fish_Audio_API_KEY spelling; never expose it to the browser.
    fish_audio_api_key: SecretStr | None = Field(
        None,
        validation_alias=AliasChoices("FISH_AUDIO_API_KEY", "Fish_Audio_API_KEY"),
    )
    fish_audio_base_url: str = Field("https://api.fish.audio", alias="FISH_AUDIO_BASE_URL")
    fish_audio_hinaa_voice_id: str = Field("", alias="FISH_AUDIO_HINAA_VOICE_ID")
    fish_audio_hiro_voice_id: str = Field("", alias="FISH_AUDIO_HIRO_VOICE_ID")
    fish_audio_model_id: str = Field("fish-speech-1.5", alias="FISH_AUDIO_MODEL_ID")
    fish_audio_output_format: str = Field("mp3", alias="FISH_AUDIO_OUTPUT_FORMAT")
    fish_audio_timeout_seconds: float = Field(30.0, alias="HINAA_FISH_AUDIO_TIMEOUT_SECONDS")
    # Deepgram — used for Hiro's voice (TTS) and STT transcription
    deepgram_api_key: SecretStr | None = Field(None, alias="Deepgram_API_KEY")
    deepgram_base_url: str = Field("https://api.deepgram.com", alias="Deepgram_BASE_URL")
    deepgram_tts_model_hiro: str = Field("aura-2-odysseus-en", alias="DEEPGRAM_TTS_MODEL_HIRO")
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "https://hinaa-workspace.vercel.app",
        ],
        alias="HINAA_ALLOWED_ORIGINS",
    )
    max_audio_bytes: int = 4 * 1024 * 1024
    max_audio_seconds: float = 20.0
    # Media (STT/TTS) calls fail fast — an 8s budget is plenty for a single
    # transcription or synthesis request.
    provider_timeout_seconds: float = 8.0
    # Stage-specific voice timeouts — each stage gets its own deadline so
    # a slow STT doesn't kill the entire turn prematurely.
    voice_stt_timeout_seconds: float = Field(12.0, alias="HINAA_VOICE_STT_TIMEOUT")
    voice_brain_first_token_timeout_seconds: float = Field(15.0, alias="HINAA_VOICE_BRAIN_TIMEOUT")
    voice_tts_phrase_timeout_seconds: float = Field(10.0, alias="HINAA_VOICE_TTS_TIMEOUT")
    voice_total_turn_timeout_seconds: float = Field(90.0, alias="HINAA_VOICE_TURN_TIMEOUT")
    # Brain (LLM) calls get a far larger budget: reasoning models such as
    # cx/gpt-5.6-sol burn hidden ``reasoning_content`` tokens before the first
    # visible token, so the old 8s media timeout killed the whole turn mid-
    # thought ("stuck in the middle" then a canned fallback reply).
    # Long-form documents need a generous ceiling: a 10k-word report takes
    # 3-4 minutes even on fast models.
    llm_timeout_seconds: float = Field(300.0, alias="HINAA_LLM_TIMEOUT_SECONDS")
    llm_stream_idle_timeout_seconds: float = Field(120.0, alias="HINAA_LLM_STREAM_IDLE_TIMEOUT_SECONDS")
    local_command_timeout_seconds: float = Field(12.0, alias="HINAA_LOCAL_COMMAND_TIMEOUT_SECONDS")
    local_stt_command: str | None = Field(None, alias="HINAA_LOCAL_STT_COMMAND")
    local_tts_command: str | None = Field(None, alias="HINAA_LOCAL_TTS_COMMAND")
    session_turn_limit: int = 24
    session_limit: int = 64
    session_history_char_limit: int = Field(32_000, alias="HINAA_SESSION_HISTORY_CHAR_LIMIT")
    # Long-form generation budget (ChatGPT-style documents/reports).
    # Brain output cap per LLM call — 16k tokens ≈ 10–12k words; the
    # continuation loop in the providers extends this further when the
    # model stops at the cap mid-document.
    llm_max_output_tokens: int = Field(16_384, alias="HINAA_LLM_MAX_OUTPUT_TOKENS")
    # Hard ceiling on streamed display text per turn (characters).
    llm_stream_char_budget: int = Field(200_000, alias="HINAA_LLM_STREAM_CHAR_BUDGET")
    # Max automatic continuations when the model stops at the token cap.
    llm_max_continuations: int = Field(8, alias="HINAA_LLM_MAX_CONTINUATIONS")
    default_companion: Literal["hinaa", "hiro"] = Field("hinaa", alias="HINAA_DEFAULT_COMPANION")
    prompt_debug_metadata: bool = Field(False, alias="HINAA_PROMPT_DEBUG_METADATA")
    personality_affection: float = Field(0.7, alias="HINAA_PERSONALITY_AFFECTION")
    personality_sass: float = Field(0.3, alias="HINAA_PERSONALITY_SASS")
    personality_energy: float = Field(0.65, alias="HINAA_PERSONALITY_ENERGY")
    personality_humor: float = Field(0.4, alias="HINAA_PERSONALITY_HUMOR")
    personality_proactivity: float = Field(0.35, alias="HINAA_PERSONALITY_PROACTIVITY")
    realtime_protocol_version: str = "1.0"
    realtime_max_frame_bytes: int = 1_280
    # Ceiling for one turn's buffered capture, in bytes. The browser sends PCM16
    # mono at its AudioContext rate of 48 kHz, so 96,000 bytes per second:
    # 2_880_000 = 30 s. Must stay above the client's 20 s force-commit, or a
    # sentence longer than the ceiling overflows and ends the live turn.
    realtime_max_buffer_bytes: int = 2_880_000
    realtime_idle_timeout_seconds: float = 35.0
    realtime_commit_timeout_seconds: float = 8.0
    # Browser-reachable origin for the realtime WebSocket (e.g. a tunnel host).
    # Unset → derived per request from the Host header; see GET /v1/realtime/url.
    realtime_public_origin: str | None = Field(None, alias="HINAA_REALTIME_PUBLIC_ORIGIN")
    database_url: str = Field(DEFAULT_LOCAL_DATABASE_URL, alias="HINAA_DATABASE_URL")
    auth_mode: Literal["dev", "oidc", "clerk"] = Field("dev", alias="HINAA_AUTH_MODE")
    dev_auth_subject: str = Field("local-dev-user", alias="HINAA_DEV_AUTH_SUBJECT")
    oidc_issuer: str | None = Field(None, alias="HINAA_OIDC_ISSUER")
    allow_oidc_scaffold_tokens: bool = Field(False, alias="HINAA_ALLOW_OIDC_SCAFFOLD_TOKENS")
    clerk_jwt_key: str | None = Field(None, alias="CLERK_JWT_KEY")
    clerk_authorized_parties: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        alias="CLERK_AUTHORIZED_PARTIES",
    )
    tinyfish_api_key: str | None = Field(None, alias="TINYFISH_API_KEY")
    github_token: SecretStr | None = Field(None, alias="GITHUB_TOKEN")
    github_default_repo: str | None = Field(None, alias="HINAA_GITHUB_DEFAULT_REPO")
    tinyfish_search_timeout_seconds: float = Field(10.0, alias="HINAA_TINYFISH_SEARCH_TIMEOUT_SECONDS")
    tinyfish_fetch_timeout_seconds: float = Field(150.0, alias="HINAA_TINYFISH_FETCH_TIMEOUT_SECONDS")
    gamma_ai_api_key: SecretStr | None = Field(None, alias="GAMMA_AI_API_KEY")
    zyte_api_key: SecretStr | None = Field(None, alias="ZYTE_API_KEY")
    freepik_api_key: SecretStr | None = Field(None, alias="FREEPIK_API_KEY")
    magnific_api_key: SecretStr | None = Field(None, alias="MAGNIFIC_API_KEY")
    freepik_model: str = Field("flux-schnell", alias="FREEPIK_DEFAULT_MODEL")
    freepik_daily_limit: int = Field(100, alias="FREEPIK_DAILY_LIMIT")
    auto_fallback_enabled: bool = Field(True, alias="HINAA_AUTO_FALLBACK_ENABLED")
    magnific_daily_soft_target_override: int | None = Field(None, alias="MAGNIFIC_DAILY_SOFT_TARGET_OVERRIDE")
    magnific_monthly_plan_credits: int = Field(45000, alias="MAGNIFIC_MONTHLY_PLAN_CREDITS")
    magnific_billing_cycle_anchor_day: int = Field(3, alias="MAGNIFIC_BILLING_CYCLE_ANCHOR_DAY")
    magnific_video_generation_enabled: bool = Field(False, alias="MAGNIFIC_VIDEO_GENERATION_ENABLED")
    video_mode: str = Field("auto_economy", alias="VIDEO_MODE")
    hinaa_allowed_user_ids: str | None = Field(None, alias="HINAA_ALLOWED_USER_IDS")
    cx_gateway_quota_url: str | None = Field(None, alias="CX_GATEWAY_QUOTA_URL")
    cx_gateway_quota_key: SecretStr | None = Field(None, alias="CX_GATEWAY_QUOTA_KEY")
    persistence_enabled: bool = Field(True, alias="HINAA_PERSISTENCE_ENABLED")
    environment: str = Field("development", alias="ENVIRONMENT")
    local_workspace_dir: Path = Field(
        Path.home() / ".hinaa" / "workspace", alias="HINAA_LOCAL_WORKSPACE_DIR"
    )
    agent_runtime_enabled: bool = Field(True, alias="HINAA_AGENT_RUNTIME_ENABLED")
    agent_max_steps: int = Field(12, ge=1, le=100, alias="HINAA_AGENT_MAX_STEPS")
    agent_max_replans: int = Field(2, ge=0, le=10, alias="HINAA_AGENT_MAX_REPLANS")
    agent_default_step_attempts: int = Field(2, ge=1, le=5, alias="HINAA_AGENT_DEFAULT_STEP_ATTEMPTS")
    agent_run_timeout_seconds: float = Field(300.0, gt=0, le=3600, alias="HINAA_AGENT_RUN_TIMEOUT_SECONDS")
    agent_default_tool_timeout_seconds: float = Field(60.0, gt=0, le=600, alias="HINAA_AGENT_DEFAULT_TOOL_TIMEOUT_SECONDS")
    agent_recovery_enabled: bool = Field(True, alias="HINAA_AGENT_RECOVERY_ENABLED")

    @model_validator(mode="after")
    def validate_generation_budgets(self) -> "Settings":
        """Clamp contradictory generation budgets at startup (directive §43).

        Dangerous combinations are *corrected* (never silently honored) and
        the corrections are recorded for the provider layer to log.
        """
        corrections: list[str] = []
        if self.llm_max_output_tokens < 256:
            corrections.append(
                f"HINAA_LLM_MAX_OUTPUT_TOKENS={self.llm_max_output_tokens} below sane minimum; clamped to 256"
            )
            object.__setattr__(self, "llm_max_output_tokens", 256)
        if self.llm_stream_char_budget < 1_000:
            corrections.append(
                f"HINAA_LLM_STREAM_CHAR_BUDGET={self.llm_stream_char_budget} below sane minimum; clamped to 1,000"
            )
            object.__setattr__(self, "llm_stream_char_budget", 1_000)
        if self.llm_max_continuations < 0:
            corrections.append("HINAA_LLM_MAX_CONTINUATIONS negative; clamped to 0")
            object.__setattr__(self, "llm_max_continuations", 0)
        if self.llm_max_continuations > 8:
            corrections.append(
                f"HINAA_LLM_MAX_CONTINUATIONS={self.llm_max_continuations} exceeds safe ceiling 8; clamped"
            )
            object.__setattr__(self, "llm_max_continuations", 8)
        if self.session_turn_limit < 2:
            corrections.append("session_turn_limit below 2; clamped")
            object.__setattr__(self, "session_turn_limit", 2)
        if self.session_history_char_limit < 1_000:
            corrections.append("session_history_char_limit below 1,000; clamped")
            object.__setattr__(self, "session_history_char_limit", 1_000)
        if self.llm_timeout_seconds < 30:
            corrections.append(
                f"HINAA_LLM_TIMEOUT_SECONDS={self.llm_timeout_seconds}s too low for long-form generation; clamped to 30s"
            )
            object.__setattr__(self, "llm_timeout_seconds", 30.0)
        if self.llm_stream_idle_timeout_seconds < 15:
            corrections.append("llm_stream_idle_timeout below 15s; clamped")
            object.__setattr__(self, "llm_stream_idle_timeout_seconds", 15.0)
        self.generation_config_corrections = corrections
        return self

    generation_config_corrections: list[str] = []

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        env = (self.environment or "").strip().lower()
        if env == "production" and self.auth_mode == "dev":
            raise ValueError(
                "FATAL CONFIGURATION ERROR: Development authentication bypass cannot be enabled in production. "
                "Set HINAA_AUTH_MODE=clerk and configure HINAA_ALLOWED_USER_IDS."
            )
        return self

    @field_validator("allowed_origins", "clerk_authorized_parties", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("azure_speech_region", mode="before")
    @classmethod
    def strip_region(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("azure_speech_key", mode="before")
    @classmethod
    def strip_speech_key(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @property
    def azure_configured(self) -> bool:
        return bool(
            self.azure_speech_key
            and self.azure_speech_key.get_secret_value()
            and self.azure_speech_region
        )

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.get_secret_value())

    @property
    def gemini_allowed_models(self) -> list[str]:
        configured = [
            model.strip() for model in self.gemini_allowed_models_raw.split(",") if model.strip()
        ]
        models = list(configured)
        if self.gemini_model:
            if self.gemini_model in models:
                models.remove(self.gemini_model)
            models.insert(0, self.gemini_model)
        return models or [self.gemini_model]

    def resolve_gemini_model(self, requested: str | None = None) -> str:
        model = (requested or "").strip() or self.gemini_model
        if model not in self.gemini_allowed_models:
            allowed = ", ".join(self.gemini_allowed_models)
            raise ValueError(f"Gemini model is not in GEMINI_ALLOWED_MODELS: {allowed}")
        return model

    @property
    def claude_configured(self) -> bool:
        return bool(self.claude_api_key and self.claude_api_key.get_secret_value() and self.active_claude_base_url)

    @property
    def active_claude_key(self) -> SecretStr | None:
        if self.claude_api_key and self.claude_api_key.get_secret_value():
            return self.claude_api_key
        return None

    @property
    def active_claude_base_url(self) -> str | None:
        value = self.claude_base_url.strip().rstrip("/")
        return value or None

    @property
    def is_mwapi_claude_gateway(self) -> bool:
        return urlparse(self.active_claude_base_url or "").hostname == "api.mwapi.dev"

    @property
    def active_claude_protocol(self) -> Literal["anthropic", "openai-compatible"]:
        if self.claude_protocol != "auto":
            return self.claude_protocol
        # The provider's successful HINAA verification uses its Claude-compatible
        # Messages route with Bearer authorization; keep OpenAI mode opt-in.
        return "anthropic"

    def _normalize_claude_model(self, model: str) -> str:
        if self.is_mwapi_claude_gateway:
            return MWAPI_CLAUDE_MODEL_ALIASES.get(model, model)
        return model

    @property
    def active_claude_model(self) -> str:
        return self._normalize_claude_model(self.claude_model)

    @property
    def claude_allowed_models(self) -> list[str]:
        configured = [model.strip() for model in self.claude_allowed_models_raw.split(",") if model.strip()]
        if self.is_mwapi_claude_gateway and (
            not configured
            or self.claude_allowed_models_raw == OFFICIAL_CLAUDE_DEFAULT_MODELS
            or all(model in MWAPI_CLAUDE_MODEL_ALIASES for model in configured)
        ):
            # A legacy browser/backend list containing only official IDs is not
            # an intentional gateway restriction; replace it with the documented
            # gateway catalog so the model selector immediately recovers.
            configured = MWAPI_CLAUDE_DEFAULT_MODELS.split(",")
        models = [self._normalize_claude_model(model) for model in configured]
        active_model = self.active_claude_model
        if active_model and active_model not in models:
            models.insert(0, active_model)
        return list(dict.fromkeys(models))

    def resolve_claude_model(self, requested: str | None = None) -> str:
        model = self._normalize_claude_model((requested or "").strip() or self.active_claude_model)
        if model not in self.claude_allowed_models:
            allowed = ", ".join(self.claude_allowed_models)
            raise ValueError(f"Claude model is not in HINAA_CLAUDE_ALLOWED_MODELS: {allowed}")
        return model

    @property
    def qwen_configured(self) -> bool:
        return bool(self.qwen_api_key and self.qwen_api_key.get_secret_value() and self.active_qwen_base_url)

    @property
    def active_qwen_key(self) -> SecretStr | None:
        if self.qwen_api_key and self.qwen_api_key.get_secret_value():
            return self.qwen_api_key
        return None

    @property
    def active_qwen_base_url(self) -> str | None:
        value = self.qwen_base_url.strip().rstrip("/")
        return value or None

    @property
    def qwen_allowed_models(self) -> list[str]:
        configured = [model.strip() for model in self.qwen_allowed_models_raw.split(",") if model.strip()]
        models = configured or [self.qwen_model]
        if self.qwen_model and self.qwen_model not in models:
            models.insert(0, self.qwen_model)
        return list(dict.fromkeys(models))

    def resolve_qwen_model(self, requested: str | None = None) -> str:
        model = (requested or "").strip() or self.qwen_model
        if model not in self.qwen_allowed_models:
            allowed = ", ".join(self.qwen_allowed_models)
            raise ValueError(f"Qwen model is not in HINAA_QWEN_ALLOWED_MODELS: {allowed}")
        return model

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key and self.groq_api_key.get_secret_value())

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.get_secret_value())

    @property
    def custom_configured(self) -> bool:
        return bool(
            (self.openai_codex_api_key and self.openai_codex_api_key.get_secret_value() and self.openai_codex_base_url)
            or (self.codecraft_api_key and self.codecraft_api_key.get_secret_value() and self.active_codecraft_base_url)
        )

    @property
    def agent_router_configured(self) -> bool:
        return bool(
            self.agent_router_api_key
            and self.agent_router_api_key.get_secret_value()
            and self.active_agent_router_base_url
        )

    @property
    def codecraft_configured(self) -> bool:
        return bool(
            self.codecraft_api_key
            and self.codecraft_api_key.get_secret_value()
            and self.active_codecraft_base_url
        )

    @property
    def youcom_configured(self) -> bool:
        return bool(self.youcom_api_key and self.youcom_api_key.get_secret_value())

    @property
    def magnific_configured(self) -> bool:
        primary = self.magnific_api_key and self.magnific_api_key.get_secret_value().strip()
        fallback = self.freepik_api_key and self.freepik_api_key.get_secret_value().strip()
        return bool(primary or fallback)

    @property
    def cx_gateway_configured(self) -> bool:
        return bool(
            self.cx_gateway_api_key
            and self.cx_gateway_api_key.get_secret_value()
            and self.cx_gateway_base_url
        )

    @property
    def active_cx_key(self) -> SecretStr | None:
        if self.cx_gateway_api_key and self.cx_gateway_api_key.get_secret_value():
            return self.cx_gateway_api_key
        return None

    @property
    def cx_allowed_models(self) -> list[str]:
        models = [m.strip() for m in self.cx_gateway_allowed_models_raw.split(",") if m.strip()]
        return models or [self.cx_gateway_model]

    @property
    def active_cx_base_url(self) -> str | None:
        value = (self.cx_gateway_base_url or "").strip().rstrip("/")
        if not value:
            return None
        return value if value.endswith("/v1") else f"{value}/v1"

    def resolve_cx_model(self, requested: str | None = None) -> str:
        model = (requested or "").strip() or self.cx_gateway_model
        if model in self.cx_allowed_models:
            return model
        if model.startswith("cx/") and model[3:] in self.cx_allowed_models:
            return model
        if f"cx/{model}" in self.cx_allowed_models:
            return model
        # Default gracefully to cx_gateway_model if requested is not listed
        return self.cx_gateway_model

    @property
    def active_freepik_key(self) -> SecretStr | None:
        return self.freepik_api_key or self.magnific_api_key

    @property
    def freepik_configured(self) -> bool:
        key = self.active_freepik_key
        return bool(key and key.get_secret_value().strip())

    @property
    def magnific_daily_credit_budget(self) -> int:
        return self.magnific_daily_soft_target_override or 1600


    @property
    def fish_audio_configured(self) -> bool:
        return bool(self.fish_audio_api_key and self.fish_audio_api_key.get_secret_value())

    @property
    def fish_audio_voice_ids(self) -> tuple[str, str]:
        return self.fish_audio_hinaa_voice_id, self.fish_audio_hiro_voice_id

    @property
    def elevenlabs_configured(self) -> bool:
        return bool(
            self.elevenlabs_api_key
            and self.elevenlabs_api_key.get_secret_value()
            and self.elevenlabs_voice_id
        )

    @property
    def deepgram_configured(self) -> bool:
        return bool(self.deepgram_api_key and self.deepgram_api_key.get_secret_value())

    @property
    def active_openai_key(self) -> SecretStr | None:
        if self.openai_api_key and self.openai_api_key.get_secret_value():
            return self.openai_api_key
        return None

    @property
    def active_openai_model(self) -> str:
        return self.openai_model

    @property
    def active_custom_key(self) -> SecretStr | None:
        if self.openai_codex_api_key and self.openai_codex_api_key.get_secret_value():
            return self.openai_codex_api_key
        if self.codecraft_api_key and self.codecraft_api_key.get_secret_value():
            return self.codecraft_api_key
        return None

    @property
    def active_custom_model(self) -> str:
        if self.openai_codex_api_key and self.openai_codex_api_key.get_secret_value():
            return self.openai_codex_model
        if self.codecraft_api_key and self.codecraft_api_key.get_secret_value():
            return self.codecraft_model
        return self.openai_codex_model

    @property
    def custom_allowed_models(self) -> list[str]:
        configured = [
            model.strip()
            for model in self.openai_codex_allowed_models_raw.split(",")
            if model.strip()
        ]
        if self.codecraft_configured:
            configured.extend(self.codecraft_allowed_models)
        models = list(dict.fromkeys(configured)) or [self.active_custom_model]
        if self.active_custom_model and self.active_custom_model not in models:
            models.insert(0, self.active_custom_model)
        return models

    def resolve_custom_model(self, requested: str | None = None) -> str:
        model = (requested or "").strip() or self.active_custom_model
        if "*" not in self.custom_allowed_models and model not in self.custom_allowed_models:
            allowed = ", ".join(self.custom_allowed_models)
            raise ValueError(
                f"Custom gateway model is not in OPENAI_CODEX_ALLOWED_MODELS: {allowed}"
            )
        return model

    @property
    def active_custom_base_url(self) -> str | None:
        value = (self.openai_codex_base_url or "").strip().rstrip("/")
        if not value and self.codecraft_configured:
            return self.active_codecraft_base_url
        if not value:
            return None
        return value if value.endswith("/v1") else f"{value}/v1"

    @property
    def openai_allowed_models(self) -> list[str]:
        configured = [
            model.strip() for model in self.openai_allowed_models_raw.split(",") if model.strip()
        ]
        models = configured or ["gpt-5-mini"]
        if self.openai_model and self.openai_model not in models:
            models.append(self.openai_model)
        return models

    def resolve_openai_model(self, requested: str | None = None) -> str:
        model = (requested or "").strip() or self.active_openai_model
        if model not in self.openai_allowed_models:
            allowed = ", ".join(self.openai_allowed_models)
            raise ValueError(f"OpenAI model is not in HINAA_OPENAI_ALLOWED_MODELS: {allowed}")
        return model

    @property
    def active_agent_router_key(self) -> SecretStr | None:
        if self.agent_router_api_key and self.agent_router_api_key.get_secret_value():
            return self.agent_router_api_key
        return None

    @property
    def active_agent_router_model(self) -> str:
        return self.agent_router_model

    @property
    def active_agent_router_base_url(self) -> str | None:
        value = (self.agent_router_base_url or "").strip().rstrip("/")
        if not value:
            return None
        if value.endswith("/dashboard"):
            value = value[:-10].rstrip("/")
        return value if value.endswith("/v1") else f"{value}/v1"

    @property
    def agent_router_allowed_models(self) -> list[str]:
        configured = [
            model.strip()
            for model in self.agent_router_allowed_models_raw.split(",")
            if model.strip()
        ]
        models = configured or [self.agent_router_model]
        if self.agent_router_model and self.agent_router_model not in models:
            models.insert(0, self.agent_router_model)
        return models

    def resolve_agent_router_model(self, requested: str | None = None) -> str:
        model = (requested or "").strip() or self.active_agent_router_model
        if "*" not in self.agent_router_allowed_models and model not in self.agent_router_allowed_models:
            allowed = ", ".join(self.agent_router_allowed_models)
            raise ValueError(
                f"Agent router model is not in AGENT_ROUTER_ALLOWED_MODELS: {allowed}"
            )
        return model

    @property
    def active_codecraft_key(self) -> SecretStr | None:
        if self.codecraft_api_key and self.codecraft_api_key.get_secret_value():
            return self.codecraft_api_key
        return None

    @property
    def active_codecraft_model(self) -> str:
        return self.codecraft_model

    @property
    def active_codecraft_base_url(self) -> str | None:
        value = (self.codecraft_base_url or "").strip().rstrip("/")
        if not value:
            return None
        if value.endswith("/dashboard"):
            value = value[:-10].rstrip("/")
        return value if value.endswith("/v1") else f"{value}/v1"

    @property
    def codecraft_allowed_models(self) -> list[str]:
        configured = [
            model.strip()
            for model in self.codecraft_allowed_models_raw.split(",")
            if model.strip()
        ]
        models = configured or [self.codecraft_model]
        if self.codecraft_model and self.codecraft_model not in models:
            models.insert(0, self.codecraft_model)
        return list(dict.fromkeys(models))

    def resolve_codecraft_model(self, requested: str | None = None) -> str:
        model = (requested or "").strip() or self.active_codecraft_model
        if "*" not in self.codecraft_allowed_models and model not in self.codecraft_allowed_models:
            allowed = ", ".join(self.codecraft_allowed_models)
            raise ValueError(
                f"CodeCraft model is not in CODE_CRAFT_ALLOWED_MODELS: {allowed}"
            )
        return model

    @property
    def ollama_configured(self) -> bool:
        return bool(self.ollama_base_url and self.ollama_base_url.strip())

    @property
    def active_ollama_base_url(self) -> str:
        value = (self.ollama_base_url or "http://localhost:11434").strip().rstrip("/")
        return value

    @property
    def active_ollama_model(self) -> str:
        return self.ollama_model or "dolphin-mistral:7b"

    @property
    def ollama_allowed_models(self) -> list[str]:
        configured = [
            m.strip()
            for m in self.ollama_allowed_models_raw.split(",")
            if m.strip()
        ]
        return configured or ["*"]

    def resolve_ollama_model(self, requested: str | None = None) -> str:
        model = (requested or "").strip() or self.active_ollama_model
        if "*" not in self.ollama_allowed_models and model not in self.ollama_allowed_models:
            allowed = ", ".join(self.ollama_allowed_models)
            raise ValueError(f"Ollama model is not in OLLAMA_ALLOWED_MODELS: {allowed}")
        return model

    @property
    def active_openai_key_label(self) -> Literal["primary", "codex", "none"]:
        if self.active_openai_key is None:
            return "none"
        return "primary"

    @property
    def local_stt_configured(self) -> bool:
        return bool(self.local_stt_command and self.local_stt_command.strip())

    @property
    def local_tts_configured(self) -> bool:
        return bool(self.local_tts_command and self.local_tts_command.strip())

    @property
    def has_voice_provider(self) -> bool:
        return self.elevenlabs_configured or (
            bool(self.azure_speech_key and self.azure_speech_key.get_secret_value())
            and bool(self.azure_speech_region)
        )

    def missing_real_configuration(self) -> list[str]:
        missing: list[str] = []
        if not self.has_voice_provider:
            missing.append("ELEVENLABS_API_KEY (or AZURE_SPEECH_KEY + AZURE_SPEECH_REGION)")
        if not self.gemini_api_key or not self.gemini_api_key.get_secret_value():
            missing.append("GEMINI_API_KEY")
        return missing

    def missing_openai_voice_configuration(self) -> list[str]:
        missing: list[str] = []
        if not self.has_voice_provider:
            missing.append("ELEVENLABS_API_KEY (or AZURE_SPEECH_KEY + AZURE_SPEECH_REGION)")
        if self.active_openai_key is None:
            missing.append("OPENAI_API_KEY")
        return missing

    def missing_custom_voice_configuration(self) -> list[str]:
        missing: list[str] = []
        if not self.has_voice_provider:
            missing.append("ELEVENLABS_API_KEY (or AZURE_SPEECH_KEY + AZURE_SPEECH_REGION)")
        if not self.openai_codex_api_key or not self.openai_codex_api_key.get_secret_value():
            missing.append("OPENAI_CODEX_API_KEY")
        if not self.active_custom_base_url:
            missing.append("OPENAI_CODEX_BASE_URL")
        return missing

    def missing_agent_router_voice_configuration(self) -> list[str]:
        missing: list[str] = []
        if not self.has_voice_provider:
            missing.append("ELEVENLABS_API_KEY (or AZURE_SPEECH_KEY + AZURE_SPEECH_REGION)")
        if not self.agent_router_api_key or not self.agent_router_api_key.get_secret_value():
            missing.append("AGENT_ROUTER_API_KEY")
        return missing


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Config profiles (directive §44) — sane bundles instead of 100 env knobs.
# Explicit env vars always override profile values.
# ---------------------------------------------------------------------------

def apply_config_profile(profile: str | None) -> dict[str, object]:
    """Apply a named profile by setting env defaults for any unset vars.

    Returns the env-var overrides applied (or {} when the profile is
    unknown). Called before :func:`get_settings` builds the Settings
    object, so real environment variables still win.
    """
    profiles: dict[str, dict[str, str]] = {
        # Low-end machines / cheap quotas: short outputs, few continuations.
        "LOW_RESOURCE": {
            "HINAA_LLM_MAX_OUTPUT_TOKENS": "4096",
            "HINAA_LLM_MAX_CONTINUATIONS": "1",
            "HINAA_LLM_STREAM_CHAR_BUDGET": "32_000",
            "HINAA_LLM_TIMEOUT_SECONDS": "120",
            "HINAA_SESSION_TURN_LIMIT": "12",
            "HINAA_SESSION_HISTORY_CHAR_LIMIT": "8_000",
        },
        # The default experience.
        "BALANCED": {
            "HINAA_LLM_MAX_OUTPUT_TOKENS": "16_384",
            "HINAA_LLM_MAX_CONTINUATIONS": "4",
            "HINAA_LLM_STREAM_CHAR_BUDGET": "200_000",
            "HINAA_LLM_TIMEOUT_SECONDS": "300",
            "HINAA_SESSION_TURN_LIMIT": "24",
            "HINAA_SESSION_HISTORY_CHAR_LIMIT": "32_000",
        },
        # Maximum long-form quality: more continuation rounds, larger memory.
        "MAX_QUALITY": {
            "HINAA_LLM_MAX_OUTPUT_TOKENS": "32_768",
            "HINAA_LLM_MAX_CONTINUATIONS": "6",
            "HINAA_LLM_STREAM_CHAR_BUDGET": "400_000",
            "HINAA_LLM_TIMEOUT_SECONDS": "600",
            "HINAA_SESSION_TURN_LIMIT": "32",
            "HINAA_SESSION_HISTORY_CHAR_LIMIT": "64_000",
        },
        # Coding/agent work: tighter latency, fewer continuations.
        "DEVELOPER": {
            "HINAA_LLM_MAX_OUTPUT_TOKENS": "16_384",
            "HINAA_LLM_MAX_CONTINUATIONS": "2",
            "HINAA_LLM_STREAM_CHAR_BUDGET": "150_000",
            "HINAA_LLM_TIMEOUT_SECONDS": "240",
            "HINAA_SESSION_TURN_LIMIT": "24",
            "HINAA_SESSION_HISTORY_CHAR_LIMIT": "32_000",
        },
    }
    name = (profile or "").strip().upper()
    if not name or name not in profiles:
        return {}
    applied: dict[str, object] = {}
    for key, value in profiles[name].items():
        if not os.environ.get(key):
            os.environ[key] = value
            applied[key] = value
    return applied


def validate_generation_settings() -> list[str]:
    """Return startup warnings for generation budgets.

    Contradictions are already clamped by the model validator; this surfaces
    the corrections plus remaining advisory warnings for the provider layer
    to log once per process.
    """
    try:
        settings = get_settings()
    except Exception:  # pragma: no cover
        return []
    warnings: list[str] = []
    warnings.extend(settings.generation_config_corrections)
    if settings.llm_max_output_tokens > 32_768:
        warnings.append(
            "HINAA_LLM_MAX_OUTPUT_TOKENS above 32,768 — most models cap lower; the provider will reject the value"
        )
    if (
        settings.llm_max_continuations >= 6
        and settings.llm_max_output_tokens >= 32_768
        and settings.llm_timeout_seconds < 300
    ):
        warnings.append(
            "continuations>=6 with 32k tokens and <300s timeout will truncate long documents on timeout"
        )
    if settings.llm_stream_char_budget > 400_000:
        warnings.append(
            "HINAA_LLM_STREAM_CHAR_BUDGET above 400k chars — turn payloads may exceed client limits"
        )
    return warnings
