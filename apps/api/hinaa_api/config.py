from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env.local"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        populate_by_name=True,
    )

    provider_mode: Literal["mock", "local", "groq", "openai", "custom", "real", "agent-router", "cx-gateway", "gemini-live"] = Field(
        "mock", alias="HINAA_PROVIDER_MODE"
    )
    azure_speech_key: SecretStr | None = Field(None, alias="AZURE_SPEECH_KEY")
    azure_speech_region: str | None = Field(None, alias="AZURE_SPEECH_REGION")
    gemini_api_key: SecretStr | None = Field(None, alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-3.6-flash", alias="GEMINI_MODEL")
    gemini_allowed_models_raw: str = Field(
        (
            "gemini-3.6-flash,gemini-3.5-flash,gemini-3.5-flash-lite,"
            "gemini-3.1-flash-lite,gemini-3-flash-preview,gemini-2.5-flash,"
            "gemini-2.5-flash-lite,gemini-2.0-flash,gemini-flash-latest,"
            "gemini-flash-lite-latest,gemini-pro-latest"
        ),
        alias="GEMINI_ALLOWED_MODELS",
    )
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
    agent_router_api_key: SecretStr | None = Field(None, alias="AGENT_ROUTER_API_KEY")
    agent_router_model: str = Field("gpt-5.6-sol", alias="AGENT_ROUTER_MODEL")
    agent_router_base_url: str | None = Field(None, alias="AGENT_ROUTER_BASE_URL")
    agent_router_allowed_models_raw: str = Field(
        "gpt-5.6-sol,claude-opus-4.8,opus-5",
        alias="AGENT_ROUTER_ALLOWED_MODELS",
    )
    azure_speech_female_voice: str = Field("ne-NP-HemkalaNeural", alias="AZURE_SPEECH_FEMALE_VOICE")
    azure_speech_male_voice: str = Field("ne-NP-SagarNeural", alias="AZURE_SPEECH_MALE_VOICE")
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
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"],
        alias="HINAA_ALLOWED_ORIGINS",
    )
    max_audio_bytes: int = 4 * 1024 * 1024
    max_audio_seconds: float = 20.0
    # Media (STT/TTS) calls fail fast — an 8s budget is plenty for a single
    # transcription or synthesis request.
    provider_timeout_seconds: float = 8.0
    # Brain (LLM) calls get a far larger budget: reasoning models such as
    # cx/gpt-5.6-sol burn hidden ``reasoning_content`` tokens before the first
    # visible token, so the old 8s media timeout killed the whole turn mid-
    # thought ("stuck in the middle" then a canned fallback reply).
    llm_timeout_seconds: float = Field(60.0, alias="HINAA_LLM_TIMEOUT_SECONDS")
    local_command_timeout_seconds: float = Field(12.0, alias="HINAA_LOCAL_COMMAND_TIMEOUT_SECONDS")
    local_stt_command: str | None = Field(None, alias="HINAA_LOCAL_STT_COMMAND")
    local_tts_command: str | None = Field(None, alias="HINAA_LOCAL_TTS_COMMAND")
    session_turn_limit: int = 8
    session_limit: int = 64
    session_history_char_limit: int = Field(4_000, alias="HINAA_SESSION_HISTORY_CHAR_LIMIT")
    default_companion: Literal["hinaa", "hiro"] = Field("hinaa", alias="HINAA_DEFAULT_COMPANION")
    prompt_debug_metadata: bool = Field(False, alias="HINAA_PROMPT_DEBUG_METADATA")
    personality_affection: float = Field(0.7, alias="HINAA_PERSONALITY_AFFECTION")
    personality_sass: float = Field(0.3, alias="HINAA_PERSONALITY_SASS")
    personality_energy: float = Field(0.65, alias="HINAA_PERSONALITY_ENERGY")
    personality_humor: float = Field(0.4, alias="HINAA_PERSONALITY_HUMOR")
    personality_proactivity: float = Field(0.35, alias="HINAA_PERSONALITY_PROACTIVITY")
    realtime_protocol_version: str = "1.0"
    realtime_max_frame_bytes: int = 1_280
    realtime_max_buffer_bytes: int = 320_000
    realtime_idle_timeout_seconds: float = 35.0
    realtime_commit_timeout_seconds: float = 8.0
    database_url: str = Field("sqlite+pysqlite:///:memory:", alias="HINAA_DATABASE_URL")
    auth_mode: Literal["dev", "oidc"] = Field("dev", alias="HINAA_AUTH_MODE")
    dev_auth_subject: str = Field("local-dev-user", alias="HINAA_DEV_AUTH_SUBJECT")
    oidc_issuer: str | None = Field(None, alias="HINAA_OIDC_ISSUER")
    allow_oidc_scaffold_tokens: bool = Field(False, alias="HINAA_ALLOW_OIDC_SCAFFOLD_TOKENS")
    persistence_enabled: bool = Field(True, alias="HINAA_PERSISTENCE_ENABLED")

    @field_validator("allowed_origins", mode="before")
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
        models = configured or [self.gemini_model]
        if self.gemini_model and self.gemini_model not in models:
            models.insert(0, self.gemini_model)
        return models

    def resolve_gemini_model(self, requested: str | None = None) -> str:
        model = (requested or "").strip() or self.gemini_model
        if model not in self.gemini_allowed_models:
            allowed = ", ".join(self.gemini_allowed_models)
            raise ValueError(f"Gemini model is not in GEMINI_ALLOWED_MODELS: {allowed}")
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
            self.openai_codex_api_key
            and self.openai_codex_api_key.get_secret_value()
            and self.openai_codex_base_url
        )

    @property
    def agent_router_configured(self) -> bool:
        return bool(
            self.agent_router_api_key
            and self.agent_router_api_key.get_secret_value()
        )

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
        if model not in self.cx_allowed_models:
            allowed = ", ".join(self.cx_allowed_models)
            raise ValueError(f"CX gateway model not in CX_GATEWAY_ALLOWED_MODELS: {allowed}")
        return model


    @property
    def elevenlabs_configured(self) -> bool:
        return bool(
            self.elevenlabs_api_key
            and self.elevenlabs_api_key.get_secret_value()
            and self.elevenlabs_voice_id
        )

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
        return None

    @property
    def active_custom_model(self) -> str:
        return self.openai_codex_model

    @property
    def custom_allowed_models(self) -> list[str]:
        configured = [
            model.strip()
            for model in self.openai_codex_allowed_models_raw.split(",")
            if model.strip()
        ]
        models = configured or [self.openai_codex_model]
        if self.openai_codex_model and self.openai_codex_model not in models:
            models.insert(0, self.openai_codex_model)
        return models

    def resolve_custom_model(self, requested: str | None = None) -> str:
        model = (requested or "").strip() or self.active_custom_model
        if model not in self.custom_allowed_models:
            allowed = ", ".join(self.custom_allowed_models)
            raise ValueError(
                f"Custom gateway model is not in OPENAI_CODEX_ALLOWED_MODELS: {allowed}"
            )
        return model

    @property
    def active_custom_base_url(self) -> str | None:
        value = (self.openai_codex_base_url or "").strip().rstrip("/")
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
        if model not in self.agent_router_allowed_models:
            allowed = ", ".join(self.agent_router_allowed_models)
            raise ValueError(
                f"Agent router model is not in AGENT_ROUTER_ALLOWED_MODELS: {allowed}"
            )
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
