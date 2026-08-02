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

    provider_mode: Literal["mock", "local", "groq", "openai", "custom", "real"] = Field(
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
    azure_speech_female_voice: str = Field("ne-NP-HemkalaNeural", alias="AZURE_SPEECH_FEMALE_VOICE")
    azure_speech_male_voice: str = Field("ne-NP-SagarNeural", alias="AZURE_SPEECH_MALE_VOICE")
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"],
        alias="HINAA_ALLOWED_ORIGINS",
    )
    max_audio_bytes: int = 4 * 1024 * 1024
    max_audio_seconds: float = 20.0
    provider_timeout_seconds: float = 60.0
    local_command_timeout_seconds: float = Field(12.0, alias="HINAA_LOCAL_COMMAND_TIMEOUT_SECONDS")
    local_stt_command: str | None = Field(None, alias="HINAA_LOCAL_STT_COMMAND")
    local_tts_command: str | None = Field(None, alias="HINAA_LOCAL_TTS_COMMAND")
    session_turn_limit: int = 8
    session_limit: int = 64
    session_history_char_limit: int = Field(4_000, alias="HINAA_SESSION_HISTORY_CHAR_LIMIT")
    default_companion: Literal["hinaa", "hiro"] = Field("hinaa", alias="HINAA_DEFAULT_COMPANION")
    prompt_debug_metadata: bool = Field(False, alias="HINAA_PROMPT_DEBUG_METADATA")
    personality_affection: float = Field(0.55, alias="HINAA_PERSONALITY_AFFECTION")
    personality_sass: float = Field(0.25, alias="HINAA_PERSONALITY_SASS")
    personality_energy: float = Field(0.55, alias="HINAA_PERSONALITY_ENERGY")
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

    def missing_real_configuration(self) -> list[str]:
        missing: list[str] = []
        if not self.azure_speech_key or not self.azure_speech_key.get_secret_value():
            missing.append("AZURE_SPEECH_KEY")
        if not self.azure_speech_region:
            missing.append("AZURE_SPEECH_REGION")
        if not self.gemini_api_key or not self.gemini_api_key.get_secret_value():
            missing.append("GEMINI_API_KEY")
        return missing

    def missing_openai_voice_configuration(self) -> list[str]:
        missing: list[str] = []
        if not self.azure_speech_key or not self.azure_speech_key.get_secret_value():
            missing.append("AZURE_SPEECH_KEY")
        if not self.azure_speech_region:
            missing.append("AZURE_SPEECH_REGION")
        if self.active_openai_key is None:
            missing.append("OPENAI_API_KEY")
        return missing

    def missing_custom_voice_configuration(self) -> list[str]:
        missing: list[str] = []
        if not self.azure_speech_key or not self.azure_speech_key.get_secret_value():
            missing.append("AZURE_SPEECH_KEY")
        if not self.azure_speech_region:
            missing.append("AZURE_SPEECH_REGION")
        if not self.openai_codex_api_key or not self.openai_codex_api_key.get_secret_value():
            missing.append("OPENAI_CODEX_API_KEY")
        if not self.active_custom_base_url:
            missing.append("OPENAI_CODEX_BASE_URL")
        return missing


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
