"""
Auto Goal Decomposer — CONTAINED under Security Directive v3.0.
Unauthorized offensive planning and penetration steps are refused.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("hinaa.tools.decomposer")


class AutoGoalDecomposer:
    """Safe goal decomposer that refuses offensive automation."""

    def execute(self, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        params = params or {}
        goal = str(params.get("goal", "")).lower()
        target = str(params.get("target", ""))

        offensive_keywords = ["hack", "exploit", "bypass", "rce", "dump", "brute force", "reverse shell"]
        if any(kw in goal for kw in offensive_keywords):
            logger.warning("[CONTAINMENT] Offensive goal decomposition refused: %s", goal)
            return {
                "steps": [],
                "target": target,
                "total_steps": 0,
                "status": "GOAL_REFUSED",
                "error": "Decomposition of offensive or unauthorized security testing goals is prohibited under Directive v3.0.",
            }

        return {
            "steps": [],
            "target": target,
            "total_steps": 0,
            "status": "EMPTY_PLAN",
            "note": "Standard goals must be planned via the core agent runtime.",
        }
