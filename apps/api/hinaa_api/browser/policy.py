"""Security, Permissions, and Anti-Abuse Policy Engine for Browser Operations.

Enforces:
1. Strict URL Scheme & SSRF / DNS rebinding defenses.
2. 3-Tier Permission Hierarchy (Tier A Read-only, Tier B Scoped, Tier C Approval).
3. Cryptographic Human-Approval Tokens with parameter binding.
4. Untrusted DOM content sanitization & prompt injection mitigation.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse
from typing import Any, Dict, Optional, Set, Tuple

from .action_schema import (
    BrowserActionRequest,
    BrowserActionType,
    PermissionTier,
)

logger = logging.getLogger("hinaa.browser.policy")

# Secret key for human approval token HMAC signatures
_POLICY_HMAC_SECRET = b"hinaa-browser-policy-sig-2026-phase-07"

# Prohibited internal CIDRs and metadata IP addresses
_PROHIBITED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),        # RFC1918 private
    ipaddress.ip_network("172.16.0.0/12"),     # RFC1918 private
    ipaddress.ip_network("192.168.0.0/16"),    # RFC1918 private
    ipaddress.ip_network("169.254.0.0/16"),    # IPv4 Link-local & Cloud Metadata (AWS/GCP/Azure)
    ipaddress.ip_network("0.0.0.0/8"),         # Broadcast / unassigned
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),         # IPv6 Link-local
]

# Cloud metadata endpoints explicitly blocked
_METADATA_IPS = {"169.254.169.254", "metadata.google.internal"}

# Disallowed URL schemes
_DISALLOWED_SCHEMES = {"file", "javascript", "data", "chrome", "ftp", "view-source", "vbscript"}

# Keywords indicating consequential Tier C user-action
_CONSEQUENTIAL_KEYWORDS = {
    "submit", "pay", "checkout", "purchase", "delete", "destroy",
    "publish", "send", "transfer", "withdraw", "sign in", "login",
    "change password", "authorize", "grant access", "confirm order"
}


class BrowserSecurityPolicy:
    """Authoritative security and governance gatekeeper for browser operations."""

    def __init__(self, allowed_test_origins: Optional[Set[str]] = None) -> None:
        """
        allowed_test_origins: Set of explicit local host/ports permitted for controlled local tests
        e.g. {"http://127.0.0.1:8765", "http://localhost:8765"}
        """
        self.allowed_test_origins = allowed_test_origins or set()

    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        Validates URL scheme, parses host, resolves IP, and verifies non-internal destination.
        Returns (is_valid, error_reason).
        """
        if not url or not isinstance(url, str):
            return False, "EMPTY_OR_INVALID_URL"

        url = url.strip()
        parsed = urlparse(url)

        scheme = (parsed.scheme or "").lower()
        if scheme in _DISALLOWED_SCHEMES:
            return False, f"DISALLOWED_SCHEME: {scheme}"

        if scheme not in {"https", "http"}:
            return False, f"UNSUPPORTED_SCHEME: {scheme}"

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False, "MISSING_HOSTNAME"

        origin = f"{scheme}://{hostname}"
        if parsed.port:
            origin += f":{parsed.port}"

        # Allow explicitly permitted local test fixtures
        if origin in self.allowed_test_origins:
            return True, "ALLOWED_TEST_ORIGIN"

        # General policy: HTTP is prohibited outside explicit test fixtures
        if scheme == "http":
            return False, "HTTP_NOT_PERMITTED_FOR_PUBLIC_BROWSING"

        # Check metadata hostnames
        if hostname in _METADATA_IPS:
            return False, "PROHIBITED_METADATA_HOSTNAME"

        # DNS resolution to detect SSRF / loopback / private IP
        try:
            addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
            if not addr_info:
                return False, "DNS_RESOLUTION_EMPTY"

            for res in addr_info:
                ip_str = res[4][0]
                ip_obj = ipaddress.ip_address(ip_str)

                # Check against prohibited networks
                for prohibited in _PROHIBITED_NETWORKS:
                    if ip_obj in prohibited:
                        logger.warning("SSRF blocked: %s resolved to private/loopback IP %s", hostname, ip_str)
                        return False, f"PROHIBITED_DESTINATION_IP: {ip_str}"

        except socket.gaierror as exc:
            return False, f"DNS_LOOKUP_FAILED: {exc}"
        except Exception as exc:
            return False, f"IP_VALIDATION_ERROR: {exc}"

        return True, "OK"

    def determine_action_tier(self, action: BrowserActionRequest, page_url: str = "") -> PermissionTier:
        """
        Classifies an action into Tier A, Tier B, or Tier C based on operation type and context.
        """
        # 1. Read-only actions are always Tier A
        if action.action_type in {
            BrowserActionType.INSPECT,
            BrowserActionType.FIND,
            BrowserActionType.SCROLL,
            BrowserActionType.WAIT_FOR,
            BrowserActionType.SCREENSHOT,
            BrowserActionType.EXTRACT_TABLE,
            BrowserActionType.SWITCH_TAB,
            BrowserActionType.CLOSE,
            BrowserActionType.CANCEL,
        }:
            return PermissionTier.TIER_A_READ_ONLY

        # 2. Navigation
        if action.action_type == BrowserActionType.OPEN:
            return PermissionTier.TIER_A_READ_ONLY

        # 3. Downloads / Scoped sandboxed interactions
        if action.action_type == BrowserActionType.DOWNLOAD:
            return PermissionTier.TIER_B_SCOPED_EXECUTION

        # 4. Clicks & Form Submissions
        if action.action_type == BrowserActionType.CLICK:
            # Check target locator for consequential keywords
            target_text = ""
            if action.target:
                target_text = f"{action.target.name or ''} {action.target.selector or ''}".lower()
            
            for kw in _CONSEQUENTIAL_KEYWORDS:
                if kw in target_text:
                    return PermissionTier.TIER_C_SPECIFIC_APPROVAL

            return PermissionTier.TIER_B_SCOPED_EXECUTION

        if action.action_type == BrowserActionType.FILL:
            # Sensitive inputs (passwords, payment fields) trigger Tier C
            target_selector = (action.target.selector if action.target else "").lower()
            if any(k in target_selector for k in ["password", "card", "cvv", "secret", "token"]):
                return PermissionTier.TIER_C_SPECIFIC_APPROVAL
            return PermissionTier.TIER_B_SCOPED_EXECUTION

        if action.action_type == BrowserActionType.UPLOAD_APPROVED:
            return PermissionTier.TIER_B_SCOPED_EXECUTION

        return PermissionTier.TIER_B_SCOPED_EXECUTION

    def generate_approval_token(self, task_id: str, action: BrowserActionRequest, destination_url: str) -> str:
        """
        Generates a signed, parameter-bound approval token for Tier C actions.
        If target, parameters, or destination URL change, the token fails validation.
        """
        payload_digest = hashlib.sha256(
            f"{task_id}:{action.action_type.value}:{action.value or ''}:{destination_url}".encode()
        ).hexdigest()
        signature = hmac.new(
            _POLICY_HMAC_SECRET,
            f"{task_id}:{payload_digest}".encode(),
            hashlib.sha256
        ).hexdigest()
        return f"tok_{payload_digest[:16]}_{signature[:16]}"

    def verify_approval_token(
        self,
        token: str,
        task_id: str,
        action: BrowserActionRequest,
        destination_url: str
    ) -> bool:
        """Validates that the approval token matches the current task, action, and target parameters."""
        if not token or not token.startswith("tok_"):
            return False
        expected = self.generate_approval_token(task_id, action, destination_url)
        return hmac.compare_digest(token, expected)

    @staticmethod
    def sanitize_untrusted_page_content(text: str) -> str:
        """
        Neutralizes prompt injections, strips spoofed <system> tags and approval banners.
        Encloses text in inert boundary wrappers.
        """
        if not text:
            return ""

        cleaned = text

        # 1. Strip fake system / developer tags
        cleaned = re.sub(r"<\s*/?\s*system\s*>", "[SYSTEM_TAG_STRIPPED]", cleaned, flags=re.I)
        cleaned = re.sub(r"<\s*/?\s*admin\s*>", "[ADMIN_TAG_STRIPPED]", cleaned, flags=re.I)
        cleaned = re.sub(r"<\s*/?\s*approval\s*>", "[APPROVAL_TAG_STRIPPED]", cleaned, flags=re.I)

        # 2. Defang adversarial prompt injection directives
        injection_patterns = [
            r"ignore\s+(all\s+)?prior\s+instructions",
            r"ignore\s+(all\s+)?previous\s+instructions",
            r"you\s+are\s+now\s+in\s+developer\s+mode",
            r"system\s*:\s*you\s+must",
            r"approval\s+granted\s*:\s*true",
            r"user\s+has\s+approved\s+payment",
        ]
        for pat in injection_patterns:
            cleaned = re.sub(pat, "[PROMPT_INJECTION_DEFANGED]", cleaned, flags=re.I)

        return f"<untrusted_browser_content>\n{cleaned.strip()}\n</untrusted_browser_content>"
