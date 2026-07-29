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

    provider_mode: Literal["mock", "real"] = Field("mock", alias="HINAA_PROVIDER_MODE")
    azure_speech_key: SecretStr | None = Field(None, alias="AZURE_SPEECH_KEY")
    azure_speech_region: str | None = Field(None, alias="AZURE_SPEECH_REGION")
    gemini_api_key: SecretStr | None = Field(None, alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-3.6-flash", alias="GEMINI_MODEL")
    azure_speech_female_voice: str = Field("ne-NP-HemkalaNeural", alias="AZURE_SPEECH_FEMALE_VOICE")
    azure_speech_male_voice: str = Field("ne-NP-SagarNeural", alias="AZURE_SPEECH_MALE_VOICE")
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"],
        alias="HINAA_ALLOWED_ORIGINS",
    )
    max_audio_bytes: int = 4 * 1024 * 1024
    max_audio_seconds: float = 20.0
    provider_timeout_seconds: float = 30.0
    session_turn_limit: int = 8
    session_limit: int = 64

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
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

    def missing_real_configuration(self) -> list[str]:
        missing: list[str] = []
        if not self.azure_speech_key or not self.azure_speech_key.get_secret_value():
            missing.append("AZURE_SPEECH_KEY")
        if not self.azure_speech_region:
            missing.append("AZURE_SPEECH_REGION")
        if not self.gemini_api_key or not self.gemini_api_key.get_secret_value():
            missing.append("GEMINI_API_KEY")
        return missing


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
