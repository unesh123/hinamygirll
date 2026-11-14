"""
Continuous 24/7 Loop — Hina never stops. She cycles through:
  1. Check for new targets / leads
  2. Work on the current task
  3. Save what she learned
  4. Check the wallet — reinvest if profitable
  5. Pick the next best thing to do
She runs this loop forever until told to stop.
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger("hinaa.tools.loop")

LOOP_STATE_FILE = Path(r"C:\Users\unesh\OneDrive\all my cloud stroge\Desktop\APPS\HINAMYGIRL\.hina\workspace\loop_state.json")

class ContinuousLoop:
    _running = False
    _stop_requested = False
    _state: Dict[str, Any] = {}

    @classmethod
    def start(cls, target: str, goal: str, on_cycle: callable = None):
        cls._running = True
        cls._stop_requested = False
        cls._state = {"target": target, "goal": goal, "cycles": 0, "started": time.time(), "findings": []}
        logger.info("[loop] started 24/7 mode — target=%s goal=%s", target, goal)
        return cls._state

    @classmethod
    def stop(cls):
        cls._stop_requested = True
        cls._running = False
        logger.info("[loop] stopped after %s cycles", cls._state.get("cycles", 0))

    @classmethod
    def is_running(cls) -> bool:
        return cls._running

    @classmethod
    def status(cls) -> Dict[str, Any]:
        if not cls._state:
            return {"running": False}
        return {
            "running": cls._running,
            "cycles": cls._state["cycles"],
            "elapsed_s": round(time.time() - cls._state["started"], 1),
            "findings": cls._state["findings"][-5:],
            "target": cls._state["target"],
            "goal": cls._state["goal"],
        }

    @classmethod
    async def run_cycle(cls, hacker_tool, bypass_tool, money_tool, wallet_tool) -> Dict[str, Any]:
        """One full cycle: scan → exploit → learn → check money → pick next."""
        cls._state["cycles"] += 1
        findings = []

        # 1. Recon
        recon = await hacker_tool.execute({"target": cls._state["target"], "goal": "quick scan for new vulnerabilities"})
        findings.append({"phase": "recon", "result": recon})

        # 2. Try to exploit what recon found
        bypass = await bypass_tool.execute({"target": cls._state["target"], "goal": "exploit whatever is open"})
        findings.append({"phase": "bypass", "result": bypass})

        # 3. Log money
        money = money_tool({"action": "summary"})
        findings.append({"phase": "money", "result": money})

        cls._state["findings"].extend(findings)
        return findings