"""
Multi-Agent Tree & Consciousness Swarm Tool for HINAA.

Exposes autonomous 5-role consensus swarm orchestration to the LLM agent runtime:
- Hierarchical delegation: Architect, Coder, Tester, DevSecOps, Critic.
- Zero-workspace clobbering: Isolated Git worktrees (.hina/worktrees/swarm_<id>).
- Multi-role adversarial consensus: AST validation, secret leak gating, path traversal checks.
- Atomic promotion: Auto-merges on consensus pass when configured.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from ..harness.swarm_orchestrator import (
    ConsensusVerdict,
    SwarmGoal,
    SwarmOrchestrator,
    get_swarm_orchestrator,
)
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.swarm_tool")


class SwarmOrchestrationInput(BaseModel):
    title: str = Field(..., description="High-level title for the autonomous swarm objective")
    description: str = Field(..., description="Comprehensive specifications, constraints, and acceptance criteria")
    auto_merge: bool = Field(default=False, description="Whether to atomically promote/merge worktree to HEAD upon consensus pass")
    require_unanimous: bool = True
    timeout_seconds: float = Field(default=120.0, gt=0, le=600)


async def swarm_orchestrate_handler(
    title: str,
    description: str,
    auto_merge: bool = False,
    require_unanimous: bool = True,
    timeout_seconds: float = 120.0,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Execute a 5-role adversarial multi-agent consensus cycle in an isolated worktree."""
    orchestrator = get_swarm_orchestrator()
    goal = SwarmGoal(
        title=title,
        description=description,
        auto_merge_on_pass=auto_merge,
        require_unanimous=require_unanimous,
        timeout_seconds=timeout_seconds,
    )

    try:
        report = await orchestrator.run_consensus_cycle(goal)
        return {
            "success": report.verdict in (ConsensusVerdict.UNANIMOUS_PASS, ConsensusVerdict.QUALIFIED_PASS),
            "verdict": report.verdict.value,
            "subagent_id": report.subagent_id,
            "consensus_score": report.consensus_score,
            "promoted": report.promoted,
            "role_votes": [
                {
                    "role": vote.role,
                    "approved": vote.approved,
                    "confidence": vote.confidence,
                    "findings": vote.findings,
                }
                for vote in report.role_votes
            ],
            "diff_summary": report.diff_summary,
            "critic_summary": report.critic_summary,
        }
    except Exception as exc:
        logger.exception("Swarm orchestration cycle failed: %s", exc)
        return {
            "success": False,
            "verdict": ConsensusVerdict.BLOCKED.value,
            "error": str(exc),
            "role_votes": [],
        }


swarm_tool_def = ToolDefinition(
    name="swarm_orchestrate",
    display_name="Multi-Agent Consciousness Swarm",
    description=(
        "Executes a multi-agent tree consensus cycle across Architect, Coder, Tester, "
        "DevSecOps, and Critic in an isolated Git worktree. Prevents workspace corruption, "
        "enforces secret scanning and AST test validation, and gates atomic promotion."
    ),
    parameters={
        "title": {
            "type": "string",
            "description": "Short title or objective name for the multi-agent swarm task",
        },
        "description": {
            "type": "string",
            "description": "Detailed task instructions, acceptance criteria, and invariant specifications",
        },
        "auto_merge": {
            "type": "boolean",
            "description": "If true, automatically promote and merge the worktree into main branch upon consensus pass",
        },
        "require_unanimous": {
            "type": "boolean",
            "description": "If true, requires 100% approval across all 5 roles. If false, allows qualified pass.",
        },
    },
    required_parameters=["title", "description"],
    permission_level="elevated",
    requires_confirmation=False,
    risk_level="high",
    cancellable=True,
    voice_aliases=["orchestrate swarm", "multi agent tree", "consensus swarm"],
)

registry.register(swarm_tool_def, swarm_orchestrate_handler)
