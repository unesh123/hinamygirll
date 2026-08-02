from __future__ import annotations

import hashlib
import json

PROMPT_VERSION = "tier-a-conversation-brain-1.0.0"
SAFETY_POLICY_VERSION = "safety-1.0.0"
COMPANION_PROFILE_VERSION = "companions-1.0.0"
LANGUAGE_POLICY_VERSION = "language-1.0.0"
SCHEMA_CONTRACT_VERSION = "assistant-turn-plan-1.0"


def fingerprint_layers(layer_payloads: list[dict[str, object]]) -> str:
    """Stable SHA-256 over normalized non-secret layer metadata and text."""
    canonical = json.dumps(
        layer_payloads, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
