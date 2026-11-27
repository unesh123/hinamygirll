"""
Continuous 24/7 Loop — CONTAINED & DISABLED under Security Directive v3.0.
Unbounded unmonitored autonomous execution loops are prohibited.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("hinaa.tools.loop")


class ContinuousLoop:
    """Fail-closed contained stub for continuous loop."""

    _running = False

    @classmethod
    def start(cls, target: str, goal: str, on_cycle: Optional[Callable] = None):
        logger.warning("[CONTAINMENT] Continuous autonomous loop start refused: disabled by Directive v3.0.")
        return {"status": "TOOL_CONTAINED", "running": False}

    @classmethod
    def stop(cls):
        cls._running = False

    @classmethod
    def is_running(cls) -> bool:
        return False

    @classmethod
    def status(cls) -> Dict[str, Any]:
        return {"running": False, "status": "TOOL_CONTAINED"}

    @classmethod
    async def run_cycle(cls, *args, **kwargs) -> Dict[str, Any]:
        logger.warning("[CONTAINMENT] Continuous loop cycle refused: tool disabled by Directive v3.0.")
        return {"status": "TOOL_CONTAINED", "cycles": 0}
