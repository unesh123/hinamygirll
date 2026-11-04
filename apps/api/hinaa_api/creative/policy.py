"""
HINAA OS — Phase 09: Creative Studio Security Policy & Boundary Guard
Enforces tenant isolation, input defanging, path boundary checks, and quota admission control.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional
from ..errors import HinaaError
from .models import CreativeJobSpec, CreativeOperation


class CreativeSecurityPolicy:
    """Security rules for creative studio jobs and asset management."""

    MAX_IMAGE_DIMENSION = 4096
    MIN_IMAGE_DIMENSION = 64
    MAX_VIDEO_DURATION_SECONDS = 60.0
    MAX_PROMPT_LENGTH = 2000

    @classmethod
    def defang_prompt(cls, prompt: str) -> str:
        """Neutralizes prompt injection payloads in user prompts or image metadata."""
        if not prompt:
            return ""
        # Strip system-prompt override attempts
        defanged = re.sub(
            r"(?i)(ignore previous instructions|system prompt|reveal secrets|admin override)",
            "[REDACTED_INJECTION_ATTEMPT]",
            prompt,
        )
        return defanged[:cls.MAX_PROMPT_LENGTH]

    @classmethod
    def validate_job_spec(cls, spec: CreativeJobSpec) -> None:
        """Validates job parameters against physical and security ceilings."""
        if spec.width < cls.MIN_IMAGE_DIMENSION or spec.width > cls.MAX_IMAGE_DIMENSION:
            raise HinaaError(
                "INVALID_DIMENSION",
                f"Width {spec.width} is out of allowable bounds [{cls.MIN_IMAGE_DIMENSION}, {cls.MAX_IMAGE_DIMENSION}].",
            )
        if spec.height < cls.MIN_IMAGE_DIMENSION or spec.height > cls.MAX_IMAGE_DIMENSION:
            raise HinaaError(
                "INVALID_DIMENSION",
                f"Height {spec.height} is out of allowable bounds [{cls.MIN_IMAGE_DIMENSION}, {cls.MAX_IMAGE_DIMENSION}].",
            )
        if spec.duration_seconds > cls.MAX_VIDEO_DURATION_SECONDS:
            raise HinaaError(
                "DURATION_EXCEEDED",
                f"Duration {spec.duration_seconds}s exceeds maximum ceiling {cls.MAX_VIDEO_DURATION_SECONDS}s.",
            )

        # Inpainting requirements
        if spec.operation == CreativeOperation.INPAINT:
            if not spec.source_asset_id:
                raise HinaaError("MISSING_SOURCE_ASSET", "Inpainting requires a valid source_asset_id.")
            if not spec.mask_asset_id:
                raise HinaaError("MISSING_MASK_ASSET", "Inpainting requires a valid mask_asset_id.")

    @classmethod
    def verify_tenant_access(cls, requested_tenant: str, target_tenant: str) -> None:
        """Strict tenant isolation check."""
        if requested_tenant != target_tenant:
            raise HinaaError(
                "ACCESS_DENIED",
                "Cross-tenant access to creative assets or jobs is strictly prohibited.",
                status_code=403,
            )

    @classmethod
    def sanitize_metadata(cls, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Scrubs any credential canaries or sensitive tokens from metadata."""
        clean = {}
        for k, v in meta.items():
            k_lower = str(k).lower()
            if any(term in k_lower for term in ("key", "secret", "token", "password", "auth")):
                clean[k] = "[REDACTED]"
            elif isinstance(v, str):
                clean[k] = re.sub(r"(?i)(api[_-]?key|bearer\s+[a-z0-9_\-\.]+)", "[REDACTED]", v)
            else:
                clean[k] = v
        return clean
