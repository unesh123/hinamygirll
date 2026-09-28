"""
Multi-Agent Orchestration Layer for HINAA.

Decomposes complex requests across specialized sub-agents:
- Researcher: Multi-hop web search, documentation, factual synthesis.
- Coder: Code generation, syntax diagnostics, test execution.
- Creative: Image prompt crafting, persona storytelling, expressive voice.
- Critic: Quality verification, hallucination detection, self-reflection.
- Orchestrator (Hinaa Core): Master dispatcher, coordinator, and synthesizer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Sequence


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    RESEARCHER = "researcher"
    CODER = "coder"
    CREATIVE = "creative"
    CRITIC = "critic"


@dataclass
class Subtask:
    id: str
    role: AgentRole
    objective: str
    input_data: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | executing | completed | failed
    result: str | None = None
    confidence: float = 1.0


@dataclass
class OrchestrationPlan:
    is_complex: bool
    primary_role: AgentRole
    subtasks: list[Subtask] = field(default_factory=list)
    synthesis_strategy: str = "direct"  # direct | pipeline | parallel_merge


class TaskDecomposer:
    """Analyzes user intent to determine whether multi-agent delegation is required."""

    def analyze(self, user_prompt: str) -> OrchestrationPlan:
        lowered = user_prompt.lower()
        subtasks: list[Subtask] = []

        is_coding = bool(re.search(r"\b(code|python|typescript|debug|fix bug|function|script|refactor|test|compile)\b", lowered))
        is_research = bool(re.search(r"\b(search|research|lookup|find out|who is|what is the latest|news|history)\b", lowered))
        is_creative = bool(re.search(r"\b(image|picture|draw|generate art|story|poem|write a story|roleplay)\b", lowered))

        # Check for multi-domain complexity
        domains = sum([is_coding, is_research, is_creative])

        if domains >= 2:
            task_id = 1
            if is_research:
                subtasks.append(Subtask(
                    id=f"subtask_{task_id}",
                    role=AgentRole.RESEARCHER,
                    objective=f"Gather relevant facts and background for: {user_prompt[:80]}",
                ))
                task_id += 1
            if is_coding:
                subtasks.append(Subtask(
                    id=f"subtask_{task_id}",
                    role=AgentRole.CODER,
                    objective="Generate robust code and verification steps based on findings.",
                ))
                task_id += 1
            if is_creative:
                subtasks.append(Subtask(
                    id=f"subtask_{task_id}",
                    role=AgentRole.CREATIVE,
                    objective="Draft expressive companion presentation and artistic assets.",
                ))
                task_id += 1

            # Always conclude with Critic
            subtasks.append(Subtask(
                id=f"subtask_{task_id}",
                role=AgentRole.CRITIC,
                objective="Verify accuracy, persona tone, and completeness.",
            ))

            return OrchestrationPlan(
                is_complex=True,
                primary_role=AgentRole.ORCHESTRATOR,
                subtasks=subtasks,
                synthesis_strategy="pipeline",
            )

        # Single domain focus
        if is_coding:
            primary = AgentRole.CODER
        elif is_research:
            primary = AgentRole.RESEARCHER
        elif is_creative:
            primary = AgentRole.CREATIVE
        else:
            primary = AgentRole.ORCHESTRATOR

        return OrchestrationPlan(
            is_complex=False,
            primary_role=primary,
            subtasks=[Subtask(id="task_1", role=primary, objective=user_prompt)],
            synthesis_strategy="direct",
        )


class AgentOrchestrator:
    """Coordinates execution across specialized agent roles."""

    def __init__(self) -> None:
        self.decomposer = TaskDecomposer()

    def plan_execution(self, user_prompt: str) -> OrchestrationPlan:
        return self.decomposer.analyze(user_prompt)

    def synthesize_results(
        self,
        plan: OrchestrationPlan,
        subtask_results: list[Subtask],
    ) -> dict[str, Any]:
        """Combine outputs from subagents into a unified turn result."""
        executed = [t for t in subtask_results if t.status == "completed" and t.result]
        if not executed:
            return {
                "synthesized_response": "I'm ready to help you with that!",
                "active_agents": [plan.primary_role.value],
            }

        if len(executed) == 1:
            return {
                "synthesized_response": executed[0].result,
                "active_agents": [executed[0].role.value],
            }

        # Multi-agent synthesis
        sections: list[str] = []
        for task in executed:
            if task.role == AgentRole.CRITIC:
                continue  # Critique used internally
            sections.append(task.result or "")

        return {
            "synthesized_response": "\n\n".join(sections),
            "active_agents": [t.role.value for t in executed],
            "subtask_count": len(executed),
        }


default_orchestrator = AgentOrchestrator()
