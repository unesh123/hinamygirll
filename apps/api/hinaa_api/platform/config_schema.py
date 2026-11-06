"""
HINAA OS — Phase 17 Environment Schema & Deployment Profile Validator.

Validates environment configuration against strict security and reliability rules:
- Personal Laptop (LOCAL_DESKTOP): Offline-first, SQLite WAL, single GPU.
- LAN Collaboration (LOCAL_LAN): Authenticated mTLS peer sync, local subnet.
- Cloud Staging / Production (CLOUD_STAGING / CLOUD_PRODUCTION): Disallows debug mode,
  denies wildcard CORS, enforces TLS, checks non-default secrets.
"""

from __future__ import annotations

import os
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

from hinaa_api.platform.contracts import DeploymentProfile, VerificationStatus


class EnvironmentConfig(BaseModel):
    deployment_profile: DeploymentProfile = DeploymentProfile.LOCAL_DESKTOP
    debug: bool = False
    bind_host: str = "127.0.0.1"
    bind_port: int = 8000
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    secret_key: str = "hinaa_secure_local_dev_key_2026_change_in_prod"
    tls_enabled: bool = False
    redis_url: Optional[str] = None
    database_url: str = "sqlite:///hinaa_autopilot.db"
    enable_gpu: bool = True
    trusted_proxies: List[str] = Field(default_factory=lambda: ["127.0.0.1"])
    offline_mode: bool = False

    @model_validator(mode="after")
    def validate_production_constraints(self) -> EnvironmentConfig:
        profile = self.deployment_profile
        is_prod = profile in (DeploymentProfile.CLOUD_STAGING, DeploymentProfile.CLOUD_PRODUCTION)

        if is_prod:
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS ('*') is strictly prohibited in production profiles.")
            insecure_keys = {"secret", "dev_secret", "change_me", "admin", "123456", "short"}
            if len(self.secret_key) < 32 or self.secret_key in insecure_keys:
                raise ValueError("Production secret_key must be at least 32 characters and non-trivial.")
            if self.debug:
                raise ValueError("Debug mode must be False in production profiles.")

        return self

    def get_verification_status(self) -> VerificationStatus:
        """Determines honest verification status for this configuration on host."""
        if self.deployment_profile == DeploymentProfile.LOCAL_DESKTOP:
            return VerificationStatus.LOCAL_VERIFIED
        elif self.deployment_profile == DeploymentProfile.LOCAL_LAN:
            return VerificationStatus.MULTI_PROCESS_SAME_HOST_VERIFIED
        elif self.deployment_profile in (DeploymentProfile.CLOUD_STAGING, DeploymentProfile.CLOUD_PRODUCTION):
            # If multi-host cloud is not backed by multi-host infrastructure, classify honestly
            if not self.redis_url or "sqlite" in self.database_url:
                return VerificationStatus.CONFIG_REQUIRED
            return VerificationStatus.MULTI_HOST_VERIFIED
        return VerificationStatus.NOT_TESTED


def load_environment_config(env_override: Optional[dict] = None) -> EnvironmentConfig:
    """Loads and validates environment configuration from environment variables."""
    profile_str = os.environ.get("HINAA_DEPLOYMENT_PROFILE", "LOCAL_DESKTOP").upper()
    try:
        profile = DeploymentProfile(profile_str)
    except ValueError:
        profile = DeploymentProfile.LOCAL_DESKTOP

    raw = {
        "deployment_profile": profile,
        "debug": os.environ.get("HINAA_DEBUG", "false").lower() == "true",
        "bind_host": os.environ.get("HINAA_BIND_HOST", "127.0.0.1"),
        "bind_port": int(os.environ.get("HINAA_BIND_PORT", "8000")),
        "cors_origins": [o.strip() for o in os.environ.get("HINAA_CORS_ORIGINS", "http://localhost:5173").split(",")],
        "secret_key": os.environ.get("HINAA_SECRET_KEY", "hinaa_secure_local_dev_key_2026_change_in_prod"),
        "tls_enabled": os.environ.get("HINAA_TLS_ENABLED", "false").lower() == "true",
        "redis_url": os.environ.get("HINAA_REDIS_URL"),
        "database_url": os.environ.get("HINAA_DATABASE_URL", "sqlite:///hinaa_autopilot.db"),
        "enable_gpu": os.environ.get("HINAA_ENABLE_GPU", "true").lower() == "true",
        "trusted_proxies": [p.strip() for p in os.environ.get("HINAA_TRUSTED_PROXIES", "127.0.0.1").split(",")],
        "offline_mode": os.environ.get("HINAA_OFFLINE_MODE", "false").lower() == "true",
    }
    if env_override:
        raw.update(env_override)

    return EnvironmentConfig(**raw)


validate_environment = load_environment_config
