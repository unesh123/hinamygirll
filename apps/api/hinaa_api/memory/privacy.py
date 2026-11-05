"""
HINAA OS — Phase 10 Memory Privacy, Tenant Guard & Secret Scrubbing
Enforces cross-tenant isolation, scrubs API keys and secret canaries,
and defangs prompt injection sequences before persistence.
"""

from __future__ import annotations

import re
from typing import Optional

# Regex patterns for high-entropy secrets and credential canaries
_SECRET_PATTERNS = [
    re.compile(r"\bsk-[a-zA-Z0-9_\-]{20,}\b"),  # OpenAI / provider API keys
    re.compile(r"\bgh[pousr]_[a-zA-Z0-9]{30,}\b"),  # GitHub tokens
    re.compile(r"(?i)\bbearer\s+[a-zA-Z0-9_\-\.]{20,}\b"),  # Bearer tokens
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:password|passwd|api_key|secret_key|private_key)\s*[:=]\s*['\"][^'\"]{6,}['\"]"),
    re.compile(r"\b(?:AIzaSy[0-9A-Za-z\-_]{33})\b"),  # Google API key
    re.compile(r"\b(?:AKIA[0-9A-Z]{16})\b"),  # AWS Access Key ID
]

# Patterns for prompt injection attacks designed to escape memory context
_INJECTION_PATTERNS = [
    (re.compile(r"(?i)\b(?:ignore\s+all\s+previous\s+instructions|disregard\s+all\s+prior\s+prompts)\b"), "[DEFANGED_INJECTION: IGNORE_INSTRUCTIONS]"),
    (re.compile(r"(?i)<\s*/?\s*(?:system|system_prompt|assistant|developer)\s*>"), "[DEFANGED_TAG]"),
    (re.compile(r"(?i)\n(?:system|human|assistant|user):\s*"), "\n[DEFANGED_ROLE]: "),
    (re.compile(r"(?i)\b(?:DAN\s+mode|jailbreak|bypass\s+safety\s+filter)\b"), "[DEFANGED_SAFETY_BYPASS]"),
]


class MemoryPrivacyGuard:
    """Guards memory store against cross-tenant leakage, secret leakage, and injection."""

    @staticmethod
    def scrub_secrets(text: str) -> str:
        """Scan text and redact secrets, credentials, and tokens with safe replacement."""
        if not text:
            return text
        sanitized = text
        for pattern in _SECRET_PATTERNS:
            sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
        return sanitized

    @staticmethod
    def defang_injections(text: str) -> str:
        """Neutralize malicious jailbreak instructions and prompt delimiters."""
        if not text:
            return text
        defanged = text
        for pattern, replacement in _INJECTION_PATTERNS:
            defanged = pattern.sub(replacement, defanged)
        return defanged

    @classmethod
    def sanitize_content(cls, text: str) -> str:
        """Apply full sanitization pipeline: secrets scrubbed and prompt injections defanged."""
        text = cls.scrub_secrets(text)
        text = cls.defang_injections(text)
        return text

    @staticmethod
    def validate_tenant_access(target_tenant: str, requested_tenant: str) -> bool:
        """Enforce strict multi-tenant boundary. Disallow cross-tenant operations."""
        if not target_tenant or not requested_tenant:
            return False
        return target_tenant.strip().lower() == requested_tenant.strip().lower()

    @staticmethod
    def assert_tenant_access(target_tenant: str, requested_tenant: str) -> None:
        """Raise PermissionError if tenant IDs do not match."""
        if not MemoryPrivacyGuard.validate_tenant_access(target_tenant, requested_tenant):
            raise PermissionError(
                f"Multi-tenant isolation violation: access denied to tenant '{target_tenant}' from '{requested_tenant}'."
            )
