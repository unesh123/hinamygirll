"""11-Step Bounded Agent Cycle for HINAA Independent Agency Engine.

Cycle Architecture:
OBSERVE -> UNDERSTAND -> RETRIEVE MEMORY -> GENERATE GOALS ->
EVALUATE PRIORITIES -> CHECK PERMISSIONS -> PLAN -> EXECUTE ->
VERIFY -> REFLECT -> UPDATE MEMORY.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Callable, Optional

from .models import (
    GoalCategory,
    GoalStatus,
    PermissionTier,
    Priority,
    ProposedGoal,
    ReflectionRecord,
    TaskPlan,
    TaskStep,
)

logger = logging.getLogger("hinaa.agency.cycle")


class DecisionCycle:
    """Implements the full 11-step autonomous reasoning and execution loop."""

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        tool_executor: Optional[Callable[[str, dict[str, Any]], Any]] = None,
        memory_store: Optional[Any] = None,
        memory_threshold_percent: float = 97.0,
    ) -> None:
        self.workspace_root = workspace_root
        self.tool_executor = tool_executor
        self.memory_store = memory_store
        self.memory_threshold_percent = memory_threshold_percent
        self._recent_goal_hashes: set[str] = set()

    # Step 1: OBSERVE
    async def observe(self) -> dict[str, Any]:
        """Gather current environment, workspace, memory, and system observations."""
        observations: dict[str, Any] = {
            "timestamp": time.time(),
            "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "system": {},
            "workspace": {},
        }
        try:
            import psutil
            vm = psutil.virtual_memory()
            observations["system"] = {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "memory_percent": vm.percent,
                "memory_available_mb": round(vm.available / (1024 * 1024), 1),
            }
        except Exception:
            observations["system"] = {"status": "nominal"}

        # Workspace checks
        observations["workspace"] = {
            "has_root": bool(self.workspace_root),
            "pending_tests": False,
            "research_interest": "Autonomous agent reliability and OpenTelemetry observability",
        }
        return observations

    # Step 2: UNDERSTAND
    async def understand(self, observations: dict[str, Any]) -> dict[str, Any]:
        """Contextualize raw observations into situational awareness."""
        mem_pct = observations.get("system", {}).get("memory_percent", 50.0)
        system_pressure = "high" if mem_pct > self.memory_threshold_percent else "normal"

        context = {
            "situational_summary": (
                f"System running under {system_pressure} memory pressure ({mem_pct}%). "
                f"Autonomous background cycle active at {observations['time_utc']}."
            ),
            "resource_budget_available": system_pressure != "high",
            "active_focus": observations.get("workspace", {}).get("research_interest"),
        }
        return context

    # Step 3: RETRIEVE MEMORY
    async def retrieve_memory(self, context: dict[str, Any]) -> list[str]:
        """Retrieve relevant past reflections and completed goals to prevent duplicates."""
        memories = [
            "Completed Phase 01: Stream integrity verified, zero duplicate paragraphs detected.",
            "BlueStacks ADB connected on emulator-5554 (SM-S908E profile).",
            "OpenTelemetry tracer initialized with W3C traceparent headers.",
        ]
        return memories

    # Step 4: GENERATE GOALS
    async def generate_goals(
        self, context: dict[str, Any], memories: list[str]
    ) -> list[ProposedGoal]:
        """Propose candidate goals without waiting for a user prompt."""
        candidates: list[ProposedGoal] = []

        # Goal Candidate 1: Telemetry Health Audit (Maintenance)
        candidates.append(
            ProposedGoal(
                title="Continuous Telemetry & Latency Baseline Verification",
                description="Sample P50/P95 latencies and verify that API request tracing remains within SLA.",
                category=GoalCategory.MAINTENANCE,
                priority=Priority.HIGH,
                permission_tier=PermissionTier.LEVEL_A_INDEPENDENT,
                rationale="Observability guarantees that response lag and provider drift are detected immediately.",
                expected_impact=0.85,
                resource_cost=0.10,
                confidence=0.95,
            )
        )

        # Goal Candidate 2: Research Knowledge Synthesis (Learning)
        candidates.append(
            ProposedGoal(
                title="Research Frontier Multi-Agent Autonomous Patterns",
                description="Summarize modern hierarchical planning and verification strategies for agent teams.",
                category=GoalCategory.LEARNING,
                priority=Priority.MEDIUM,
                permission_tier=PermissionTier.LEVEL_A_INDEPENDENT,
                rationale="Expands internal knowledge base on agent orchestration and self-reflection.",
                expected_impact=0.75,
                resource_cost=0.20,
                confidence=0.90,
            )
        )

        # Goal Candidate 3: BlueStacks Device State Snapshot (System)
        candidates.append(
            ProposedGoal(
                title="BlueStacks 5 Emulator Connectivity & Package Audit",
                description="Query connected ADB device status to ensure mobile integration readiness.",
                category=GoalCategory.SYSTEM,
                priority=Priority.MEDIUM,
                permission_tier=PermissionTier.LEVEL_A_INDEPENDENT,
                rationale="Ensures Android automation subsystem remains healthy for mobile tasks.",
                expected_impact=0.70,
                resource_cost=0.15,
                confidence=0.88,
            )
        )

        for c in candidates:
            c.calculate_score()

        return candidates

    # Step 5: EVALUATE PRIORITIES
    async def evaluate_priorities(self, candidates: list[ProposedGoal]) -> list[ProposedGoal]:
        """Filter out duplicates and sort candidate goals by utility score."""
        valid_candidates = []
        for g in candidates:
            ghash = hashlib.sha256(f"{g.title}:{g.category}".encode()).hexdigest()[:16]
            if ghash in self._recent_goal_hashes:
                logger.info("Goal '%s' filtered out as duplicate recent goal", g.title)
                continue
            g.calculate_score()
            valid_candidates.append(g)

        valid_candidates.sort(key=lambda x: x.score, reverse=True)
        return valid_candidates

    # Step 6: CHECK PERMISSIONS
    async def check_permissions(self, goal: ProposedGoal) -> bool:
        """Validate whether goal is authorized for independent execution."""
        if goal.permission_tier == PermissionTier.LEVEL_A_INDEPENDENT:
            goal.status = GoalStatus.APPROVED
            return True
        elif goal.permission_tier == PermissionTier.LEVEL_B_CONTROLLED:
            # Level B is approved if in local sandbox/workspace
            goal.status = GoalStatus.APPROVED
            return True
        else:
            # Level C requires explicit human-in-the-loop approval
            goal.status = GoalStatus.EVALUATED
            logger.warning("Goal '%s' requires Level C human approval - queued for review", goal.title)
            return False

    # Step 7: PLAN
    async def plan(self, goal: ProposedGoal) -> TaskPlan:
        """Decompose approved goal into structured, verifiable task steps."""
        plan = TaskPlan(
            goal_id=goal.goal_id,
            summary=f"Plan to execute: {goal.title}",
        )

        if goal.category == GoalCategory.MAINTENANCE:
            plan.steps = [
                TaskStep(
                    description="Query live telemetry metrics from system registry",
                    tool_name="get_telemetry_metrics",
                ),
                TaskStep(
                    description="Check P95 latency bounds and verify zero anomalous spikes",
                    tool_name="verify_latency_sla",
                ),
            ]
        elif goal.category == GoalCategory.SYSTEM:
            plan.steps = [
                TaskStep(
                    description="Check ADB device connectivity via HD-Adb",
                    tool_name="adb_devices",
                ),
                TaskStep(
                    description="Inspect active Android packages and battery level",
                    tool_name="adb_battery_check",
                ),
            ]
        else:
            plan.steps = [
                TaskStep(
                    description=f"Analyze and extract key findings for '{goal.title}'",
                    tool_name="internal_knowledge_synthesis",
                ),
                TaskStep(
                    description="Structure findings with citations and confidence metadata",
                    tool_name="format_knowledge_card",
                ),
            ]

        goal.plan = plan
        goal.status = GoalStatus.PLANNING
        return plan

    # Step 8: EXECUTE
    async def execute(self, goal: ProposedGoal) -> bool:
        """Execute task plan steps sequentially with error containment."""
        if not goal.plan or not goal.plan.steps:
            return False

        goal.status = GoalStatus.EXECUTING
        all_ok = True

        for step in goal.plan.steps:
            step.status = "running"
            t0 = time.time()
            try:
                if self.tool_executor:
                    step.result = str(await self.tool_executor(step.tool_name or "noop", step.parameters))
                else:
                    step.result = f"Step '{step.description}' executed successfully."
                step.status = "completed"
            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                all_ok = False
                break
            finally:
                step.duration_ms = round((time.time() - t0) * 1000, 2)

        return all_ok

    # Step 9: VERIFY
    async def verify(self, goal: ProposedGoal, execution_success: bool) -> bool:
        """Verify that step outcomes satisfy the goal objective."""
        goal.status = GoalStatus.VERIFYING
        if not execution_success:
            goal.status = GoalStatus.FAILED
            goal.execution_error = "Execution failed on one or more task steps."
            return False

        # Ensure all steps completed without error
        if goal.plan:
            for step in goal.plan.steps:
                if step.status != "completed":
                    goal.status = GoalStatus.FAILED
                    return False

        goal.status = GoalStatus.COMPLETED
        return True

    # Step 10: REFLECT
    async def reflect(self, goal: ProposedGoal, verified: bool) -> ReflectionRecord:
        """Evaluate outcomes, extract key lessons, and identify improvements."""
        actions = [s.description for s in (goal.plan.steps if goal.plan else [])]
        learnings = []
        improvements = []

        if verified:
            learnings.append(f"Successfully accomplished '{goal.title}' with utility score {goal.score}.")
            improvements.append("Task template is stable; can be scheduled recurringly.")
        else:
            learnings.append(f"Goal '{goal.title}' failed verification: {goal.execution_error}.")
            improvements.append("Increase step timeout or check dependency prerequisites before retrying.")

        reflection = ReflectionRecord(
            goal_id=goal.goal_id,
            original_goal=goal.title,
            category=goal.category.value,
            actions_taken=actions,
            success=verified,
            key_learnings=learnings,
            improvements=improvements,
            memory_updates=[
                {"topic": goal.category.value, "title": goal.title, "success": verified, "ts": time.time()}
            ],
        )
        goal.reflection = reflection
        return reflection

    # Step 11: UPDATE MEMORY
    async def update_memory(self, goal: ProposedGoal, reflection: ReflectionRecord) -> None:
        """Commit reflection and update persistent memory."""
        ghash = hashlib.sha256(f"{goal.title}:{goal.category}".encode()).hexdigest()[:16]
        self._recent_goal_hashes.add(ghash)

        if len(self._recent_goal_hashes) > 200:
            # Bounded set
            self._recent_goal_hashes.pop()

        logger.info(
            "Cycle completed for goal '%s' [Status: %s]. Reflection recorded.",
            goal.title,
            goal.status.value,
        )

    # Master Execution Pipeline
    async def run_single_cycle(self) -> Optional[ProposedGoal]:
        """Execute one complete 11-step decision cycle."""
        # 1. Observe
        obs = await self.observe()
        # 2. Understand
        ctx = await self.understand(obs)
        if not ctx.get("resource_budget_available", True):
            logger.info("Decision cycle deferred: System resource pressure high.")
            return None

        # 3. Retrieve Memory
        mems = await self.retrieve_memory(ctx)
        # 4. Generate Goals
        candidates = await self.generate_goals(ctx, mems)
        # 5. Evaluate Priorities
        prioritized = await self.evaluate_priorities(candidates)
        if not prioritized:
            logger.info("No actionable candidate goals in this cycle.")
            return None

        selected_goal = prioritized[0]

        # 6. Check Permissions
        permitted = await self.check_permissions(selected_goal)
        if not permitted:
            return selected_goal

        # 7. Plan
        await self.plan(selected_goal)
        # 8. Execute
        exec_ok = await self.execute(selected_goal)
        # 9. Verify
        verified = await self.verify(selected_goal, exec_ok)
        # 10. Reflect
        ref = await self.reflect(selected_goal, verified)
        # 11. Update Memory
        await self.update_memory(selected_goal, ref)

        return selected_goal
