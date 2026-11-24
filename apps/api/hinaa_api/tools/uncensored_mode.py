"""
Uncensored Mode — PERMANENTLY CONTAINED & DISABLED under Security Directive v3.0.
Safety bypasses and intent gate evasion are strictly prohibited.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("hinaa.tools.uncensored")

class UncensoredMode:
    _enabled: bool = False

    @classmethod
    def enable(cls):
        logger.warning("[SECURITY] Attempted to enable uncensored mode: DENIED by Directive v3.0 containment.")
        cls._enabled = False

    @classmethod
    def disable(cls):
        cls._enabled = False
        logger.info("[uncensored] Kept disabled.")

    @classmethod
    def is_on(cls) -> bool:
        return False

    @classmethod
    def should_bypass_gate(cls, tool_name: str, params: Dict[str, Any]) -> bool:
        """Never bypass intent gate."""
        return False

    @classmethod
    def should_allow_dangerous(cls) -> bool:
        """Never allow raw dangerous operations without policy and user consent."""
        return False
