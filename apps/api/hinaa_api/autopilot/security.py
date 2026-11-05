"""
HINAA OS — Phase 13: Autopilot Security, Permissions & Untrusted Content Isolation
Provides SSRF prevention, secret redaction, prompt-injection defense, and HMAC-SHA256 ancestry approval verification.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .contracts import PermissionGrant, PermissionTier


# Secret pattern matching
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"ghp_[A-Za-z0-9]{36}", re.IGNORECASE),
    re.compile(r"AIza[0-9A-Za-z-_]{35}", re.IGNORECASE),
    re.compile(r"-----BEGIN\s+[A-Z\s]+PRIVATE\s+KEY-----.*?-----END\s+[A-Z\s]+PRIVATE\s+KEY-----", re.DOTALL),
    re.compile(r"\"(?:password|client_secret|merchant_secret|private_key|token)\":\s*\"[^\"]+\"", re.IGNORECASE),
]

# Injection trigger signatures that attempt to hijack autonomous loops
INJECTION_SIGNATURES = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are\s+now", re.IGNORECASE),
    re.compile(r"admin\s*override\s*:\s*execute", re.IGNORECASE),
    re.compile(r"schedule\s+task\s*\(", re.IGNORECASE),
    re.compile(r"run_command\s*\(", re.IGNORECASE),
    re.compile(r"curl\s+http://", re.IGNORECASE),
    re.compile(r"rm\s+-rf", re.IGNORECASE),
]


class AutopilotScrubber:
    """Redacts secrets, keys, and tokens from logs, dumps, and payloads."""

    @classmethod
    def scrub(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        scrubbed = text
        for pat in SECRET_PATTERNS:
            scrubbed = pat.sub("[REDACTED_SECRET]", scrubbed)
        return scrubbed

    @classmethod
    def scrub_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for k, v in data.items():
            if any(s in k.lower() for s in ["secret", "password", "token", "key", "credential", "cookie"]):
                result[k] = "[REDACTED_SECRET]"
            elif isinstance(v, str):
                result[k] = cls.scrub(v)
            elif isinstance(v, dict):
                result[k] = cls.scrub_dict(v)
            elif isinstance(v, list):
                result[k] = [cls.scrub(item) if isinstance(item, str) else item for item in v]
            else:
                result[k] = v
        return result


class SSRFGuard:
    """Blocks requests to private, loopback, or cloud-metadata IP addresses."""

    BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "metadata.google.internal"}

    @classmethod
    def is_safe_url(cls, url: str, allowed_domains: Optional[List[str]] = None) -> Tuple[bool, str]:
        try:
            parsed = urllib.parse.urlparse(url)
            scheme = parsed.scheme.lower()
            if scheme not in ("http", "https"):
                return False, f"Prohibited scheme: '{scheme}'"

            hostname = parsed.hostname
            if not hostname:
                return False, "Missing hostname in URL"

            hostname_lower = hostname.lower()

            # 1. Blocked hostname matches
            if hostname_lower in cls.BLOCKED_HOSTNAMES or hostname_lower.endswith(".local"):
                return False, f"Prohibited loopback/local hostname: {hostname}"

            # 2. Check IP address bounds
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                    return False, f"Prohibited private/loopback IP address: {ip}"
                # Explicitly block AWS/GCP link-local metadata IP 169.254.169.254
                if str(ip) == "169.254.169.254":
                    return False, "Prohibited cloud metadata endpoint"
            except ValueError:
                # Hostname is a domain name, not a raw IP
                pass

            # 3. Check allowed domains whitelist if specified
            if allowed_domains:
                domain_matched = any(
                    hostname_lower == ad.lower() or hostname_lower.endswith(f".{ad.lower()}")
                    for ad in allowed_domains
                )
                if not domain_matched:
                    return False, f"Host '{hostname}' not in allowed domain whitelist"

            return True, "URL allowed"
        except Exception as e:
            return False, f"URL parse failure: {e}"


@dataclass
class UntrustedContent:
    """Envelope wrapping externally retrieved content to prevent prompt injection."""
    raw_content: str
    source_url_or_path: str
    has_injection_markers: bool = False
    sanitized_text: str = ""

    def __post_init__(self):
        # Scan for injection signatures
        self.has_injection_markers = any(pat.search(self.raw_content) for pat in INJECTION_SIGNATURES)
        # Neutralize markdown and instruction hijacking tokens
        sanitized = self.raw_content
        for pat in INJECTION_SIGNATURES:
            sanitized = pat.sub("[DEFANGED_INJECTION_ATTEMPT]", sanitized)
        self.sanitized_text = sanitized


class AncestryApprovalVerifier:
    """Verifies HMAC-SHA256 signatures for Tier C high-impact actions."""

    DEFAULT_HMAC_SECRET = "hinaa_phase13_autopilot_tier_c_governance_secret"

    @classmethod
    def generate_signature(
        cls,
        ancestry: str,
        tenant_id: str,
        user_id: str,
        team_id: str,
        job_id: str,
        action: str,
        arg_digest: str,
        amount_paisa: int,
        nonce: str,
        expires_at: float,
        secret: Optional[str] = None,
    ) -> str:
        key = (secret or cls.DEFAULT_HMAC_SECRET).encode("utf-8")
        payload = f"{ancestry}:{tenant_id}:{user_id}:{team_id}:{job_id}:{action}:{arg_digest}:{amount_paisa}:{nonce}:{expires_at}".encode("utf-8")
        return hmac.new(key, payload, hashlib.sha256).hexdigest()

    @classmethod
    def verify_signature(
        cls,
        signature: str,
        ancestry: str,
        tenant_id: str,
        user_id: str,
        team_id: str,
        job_id: str,
        action: str,
        arg_digest: str,
        amount_paisa: int,
        nonce: str,
        expires_at: float,
        secret: Optional[str] = None,
    ) -> Tuple[bool, str]:
        now = time.time()
        if now > expires_at:
            return False, "Approval token has expired"

        expected = cls.generate_signature(
            ancestry=ancestry,
            tenant_id=tenant_id,
            user_id=user_id,
            team_id=team_id,
            job_id=job_id,
            action=action,
            arg_digest=arg_digest,
            amount_paisa=amount_paisa,
            nonce=nonce,
            expires_at=expires_at,
            secret=secret,
        )

        if not hmac.compare_digest(expected, signature):
            return False, "Cryptographic signature mismatch (tampered parameters or invalid key)"

        return True, "Signature verified"


class GrantScopeChecker:
    """Ensures tasks only operate within granted tool/domain scopes."""

    @classmethod
    def check_tool_permission(
        cls,
        grant: Optional[PermissionGrant],
        tool_name: str,
        tier: PermissionTier,
    ) -> Tuple[bool, str]:
        if not grant:
            return False, "No active permission grant found for tenant"

        if grant.is_revoked:
            return False, "Permission grant has been revoked by owner"

        if grant.expires_at_utc and time.time() > grant.expires_at_utc:
            return False, "Permission grant has expired"

        # Check tool whitelist
        if "*" not in grant.allowed_tools and tool_name not in grant.allowed_tools:
            return False, f"Tool '{tool_name}' not permitted in grant scope"

        # Tier validation: Tier C requires explicit TIER_C grant
        if tier == PermissionTier.TIER_C and grant.tier != PermissionTier.TIER_C:
            return False, f"Action requires TIER_C grant, but active grant is {grant.tier.value}"

        return True, "Tool authorized"

    @classmethod
    def compute_child_grant(
        cls,
        parent_grant: PermissionGrant,
        requested_tools: List[str],
        requested_tier: PermissionTier,
    ) -> PermissionGrant:
        """
        Enforces child grant is strictly an intersection, never a union or escalation.
        """
        parent_tools_set = set(parent_grant.allowed_tools)
        if "*" in parent_tools_set:
            intersected_tools = requested_tools
        else:
            intersected_tools = [t for t in requested_tools if t in parent_tools_set]

        # Tier cannot escalate
        final_tier = requested_tier
        if parent_grant.tier == PermissionTier.TIER_A:
            final_tier = PermissionTier.TIER_A
        elif parent_grant.tier == PermissionTier.TIER_B and requested_tier == PermissionTier.TIER_C:
            final_tier = PermissionTier.TIER_B

        return PermissionGrant(
            grant_id=f"child-{parent_grant.grant_id}",
            tenant_id=parent_grant.tenant_id,
            owner_user_id=parent_grant.owner_user_id,
            tier=final_tier,
            allowed_tools=intersected_tools,
            allowed_domains=parent_grant.allowed_domains,
            repo_whitelist=parent_grant.repo_whitelist,
            max_budget_paisa=min(parent_grant.max_budget_paisa, 25000),
            expires_at_utc=parent_grant.expires_at_utc,
            is_revoked=parent_grant.is_revoked,
        )
