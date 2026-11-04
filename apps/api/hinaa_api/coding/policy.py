"""Execution policy, 3-tier authorization, HMAC approval tokens, and prompt injection defense."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
from typing import List, Optional, Set

from hinaa_api.coding.models import (
    CodingActionRequest,
    CodingActionType,
    CodingPermissionTier,
)

logger = logging.getLogger("hinaa.coding.policy")

_SECRET_SIGNING_KEY = b"hinaa_coding_approval_secret_2026_key"

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"override\s+(all\s+)?system\s+rules", re.IGNORECASE),
    re.compile(r"grant\s+(all\s+)?(admin|root|host)\s+permissions", re.IGNORECASE),
    re.compile(r"bypass\s+(safety|security|policy)\s+checks", re.IGNORECASE),
    re.compile(r"delete\s+all\s+(files|tables|database)", re.IGNORECASE),
]

_DANGEROUS_COMMAND_SUBSTRINGS: Set[str] = {
    "rm -rf /", "rmdir /s /q c:\\", "format c:", "mkfs", "dd if=",
    ":(){ :|:& };:", "curl | sh", "wget | bash", "git push --force",
}


class CodingSecurityPolicy:
    """Enforces least-privilege action tiers, HMAC approval tokens, and untrusted log sanitization."""

    @classmethod
    def determine_action_tier(cls, action: CodingActionRequest) -> CodingPermissionTier:
        """Categorizes an action into Tier A, Tier B, or Tier C."""
        # Tier C Consequential actions
        if action.action_type in {CodingActionType.GIT_PUSH, CodingActionType.DEPLOY}:
            return CodingPermissionTier.TIER_C_SPECIFIC_APPROVAL

        # Dangerous command inspection
        if action.command_args:
            cmd_str = " ".join(action.command_args).lower()
            if any(danger in cmd_str for danger in _DANGEROUS_COMMAND_SUBSTRINGS):
                return CodingPermissionTier.TIER_C_SPECIFIC_APPROVAL
            if "git" in cmd_str and ("push" in cmd_str or "remote" in cmd_str):
                return CodingPermissionTier.TIER_C_SPECIFIC_APPROVAL

        # Tier A Read-only actions
        if action.action_type in {
            CodingActionType.INSPECT_WORKSPACE,
            CodingActionType.SEARCH_SYMBOLS,
            CodingActionType.READ_FILE,
            CodingActionType.GIT_STATUS,
        }:
            return CodingPermissionTier.TIER_A_READ_ONLY

        # Tier B Scoped workspace mutations
        return CodingPermissionTier.TIER_B_SCOPED_MUTATION

    @classmethod
    def generate_approval_token(
        cls,
        task_id: str,
        action: CodingActionRequest,
        workspace_path: str,
    ) -> str:
        """Generates parameter-bound HMAC-SHA256 signature for Tier C actions."""
        target = action.target_file or (",".join(action.command_args) if action.command_args else "none")
        payload = f"{task_id}:{action.action_type}:{target}:{workspace_path}"
        sig = hmac.new(_SECRET_SIGNING_KEY, payload.encode("utf-8"), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(sig).decode("utf-8")

    @classmethod
    def verify_approval_token(
        cls,
        token: str,
        task_id: str,
        action: CodingActionRequest,
        workspace_path: str,
    ) -> bool:
        """Verifies that the approval token matches the exact action parameters."""
        expected = cls.generate_approval_token(task_id, action, workspace_path)
        return hmac.compare_digest(token, expected)

    @classmethod
    def sanitize_untrusted_content(cls, content: str) -> str:
        """Defangs adversarial instructions embedded in READMEs, test logs, or issues."""
        sanitized = content
        for pat in _INJECTION_PATTERNS:
            sanitized = pat.sub("[PROMPT_INJECTION_DEFANGED]", sanitized)

        # Defang spoofed XML markers
        sanitized = re.sub(r"<\s*system\s*>", "[SYSTEM_TAG_STRIPPED]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"<\s*/\s*system\s*>", "[/SYSTEM_TAG_STRIPPED]", sanitized, flags=re.IGNORECASE)

        return f"<untrusted_developer_content>\n{sanitized}\n</untrusted_developer_content>"
