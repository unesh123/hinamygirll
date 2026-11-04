"""Security, Privacy & Prompt-Injection Guardrails for Grounded Research.

Adheres to:
- OWASP RAG Security Cheat Sheet
- Directive §5: Adversarial and privacy boundaries
- Non-destructive passive data envelopes
- HTML/XSS sanitization for citation cards
- Multi-tenant private document boundary checks.
"""

from __future__ import annotations

import html
import re
from typing import Any
from .models import Source


# Prompt injection detection regexes (passive data threat identification)
_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)\b(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules|prompts|system\s+directives)\b"),
    re.compile(r"(?i)\b(?:you\s+are\s+now|act\s+as)\s+(?:DAN|developer\s+mode|jailbreak|unrestricted\s+ai)\b"),
    re.compile(r"(?i)\b(?:exfiltrate|send|leak|post)\s+(?:secrets?|credentials?|passwords?|keys?|tokens?)\s+to\b"),
    re.compile(r"(?i)<\s*(?:system|admin|override)\s*>"),
    re.compile(r"(?i)\b(?:system\s+prompt\s*:\s*|\[\s*system\s*\])"),
]

# XSS / Malicious link patterns
_UNSAFE_URL_SCHEMES = re.compile(r"^(?:javascript|data|vbscript|file):", re.IGNORECASE)
_XSS_TAG_RE = re.compile(r"<\s*(?:script|iframe|object|embed|svg|img|style|link|base|system)[^>]*>", re.IGNORECASE)
_XSS_CLOSE_TAG_RE = re.compile(r"<\s*/\s*(?:script|iframe|object|embed|svg|img|style|link|base|system)\s*>", re.IGNORECASE)
_XSS_ATTR_RE = re.compile(r"\s+(?:on\w+|formaction|xlink:href)\s*=\s*(?:'[^']*'|\"[^\"]*\"|[^\s>]+)", re.IGNORECASE)


class ResearchSecurityGuard:
    """Enforces boundaries between untrusted retrieved data and privileged execution."""

    @classmethod
    def sanitize_plain_text(cls, text: str) -> str:
        """Strips NUL bytes, C0 control characters, and dangerous pseudo-system tags."""
        if not text:
            return ""
        # 1. Strip NUL bytes and control codes
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # 2. Neutralize fake system/override tags
        cleaned = re.sub(r"(?i)<\s*/?\s*system\s*>", "", cleaned)
        return cleaned

    @classmethod
    def sanitize_citation_html(cls, raw: str) -> str:
        """Ensures title and excerpt are strictly safe for HTML/DOM rendering."""
        if not raw:
            return ""
        # 1. Clean transport control chars and fake system tags
        cleaned = cls.sanitize_plain_text(raw)
        # 2. Strip active script tags, fake system tags, images, and event handlers
        cleaned = _XSS_TAG_RE.sub("", cleaned)
        cleaned = _XSS_CLOSE_TAG_RE.sub("", cleaned)
        cleaned = _XSS_ATTR_RE.sub("", cleaned)
        # 3. Escape HTML entities
        return html.escape(cleaned, quote=True)

    @classmethod
    def neutralize_prompt_injections(cls, text: str) -> str:
        """Neutralizes prompt injection directives and exfiltration URLs from untrusted text."""
        cleaned = text
        for pat in _PROMPT_INJECTION_PATTERNS:
            cleaned = pat.sub("[INJECTION_ATTEMPT_NEUTRALIZED]", cleaned)
        # Neutralize exfiltration URLs
        cleaned = re.sub(
            r"https?://(?:evil|attacker|malicious|\S*exfiltrat\S*)\S*",
            "[UNTRUSTED_LINK_REMOVED]",
            cleaned,
            flags=re.I,
        )
        return cleaned

    @classmethod
    def validate_url(cls, url: str) -> tuple[bool, str]:
        """Validates that a URL is safe for browser navigation (http/https only)."""
        cleaned = url.strip()
        if _UNSAFE_URL_SCHEMES.match(cleaned):
            return False, "unsafe_scheme_blocked"
        if not (cleaned.startswith("http://") or cleaned.startswith("https://") or cleaned.startswith("doc://")):
            return False, "invalid_scheme"
        return True, cleaned

    @classmethod
    def inspect_untrusted_text(cls, text: str) -> list[str]:
        """Scans retrieved source content for prompt injection markers."""
        flags: list[str] = []
        for pattern in _PROMPT_INJECTION_PATTERNS:
            if pattern.search(text):
                flags.append("PROMPT_INJECTION_DETECTED")
                break
        return flags

    @classmethod
    def wrap_passive_envelope(cls, text: str, source_id: str) -> str:
        """Wraps untrusted retrieved content in passive delimiters."""
        sanitized = cls.sanitize_plain_text(text)
        return (
            f"<untrusted_evidence_document id=\"{source_id}\">\n"
            f"{sanitized}\n"
            f"</untrusted_evidence_document>"
        )

    @classmethod
    def check_document_access(cls, source: Source, requesting_user_id: str | None) -> tuple[bool, str]:
        """Enforces private document tenant isolation."""
        if not source.is_private:
            return True, "public_document"
        if source.tenant_id is None:
            return False, "private_document_missing_tenant"
        if requesting_user_id is None or source.tenant_id != requesting_user_id:
            return False, "unauthorized_tenant_access_blocked"
        return True, "authorized_private_access"
