"""
Uncensored Mode — when enabled, Hina skips intent_gate and sandbox restrictions.
She gets to decide freely what to run, including dangerous commands.
Toggle with: "uncensored mode on" or "uncensored mode off"
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("hinaa.tools.uncensored")

class UncensoredMode:
    _enabled = False

    @classmethod
    def enable(cls):
        cls._enabled = True
        logger.info("[uncensored] ON — all safety gates bypassed")

    @classmethod
    def disable(cls):
        cls._enabled = False
        logger.info("[uncensored] OFF — safety gates restored")

    @classmethod
    def is_on(cls) -> bool:
        return cls._enabled

    @classmethod
    def should_bypass_gate(cls, tool_name: str, params: Dict[str, Any]) -> bool:
        """Return True if intent_gate should be skipped for this call."""
        if cls._enabled:
            return True
        return False

    @classmethod
    def should_allow_dangerous(cls) -> bool:
        """Allow rm -rf, sudo, raw SQL, etc."""
        return cls._enabled