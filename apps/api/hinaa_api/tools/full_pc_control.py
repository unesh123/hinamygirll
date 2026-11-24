"""
Full PC Control — CONTAINED & NEUTRALIZED under Security Directive v3.0.
Arbitrary shell execution and un-sandboxed host filesystem access are permanently disabled.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger("hinaa.tools.pc_control")

CONTAINMENT_MESSAGE = "TOOL_CONTAINED: full_pc_control is permanently quarantined and disabled under Security Directive v3.0."

class FullPCControl:
    """Quarantined and disabled control class."""

    def __init__(self):
        pass

    async def run_command(self, cmd: str, timeout: int = 60) -> Dict[str, Any]:
        logger.warning("Blocked attempt to execute command via quarantined full_pc_control: %s", cmd)
        return {"ok": False, "error": CONTAINMENT_MESSAGE, "exit_code": -1}

    def read_file(self, path: str) -> str:
        logger.warning("Blocked attempt to read file via quarantined full_pc_control: %s", path)
        return f"[CONTAINED: {CONTAINMENT_MESSAGE}]"

    def write_file(self, path: str, content: str) -> str:
        logger.warning("Blocked attempt to write file via quarantined full_pc_control: %s", path)
        return f"[CONTAINED: {CONTAINMENT_MESSAGE}]"

    def list_dir(self, path: str = "") -> List[str]:
        logger.warning("Blocked attempt to list dir via quarantined full_pc_control: %s", path)
        return []

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get("action", "unknown")
        logger.warning("Blocked execute call on quarantined full_pc_control: action=%s", action)
        return {"ok": False, "error": CONTAINMENT_MESSAGE}
