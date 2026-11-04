"""Continuous Operating Runtime for HINAA Independent Agency Engine.

Drives background wake cycles, task prioritization, resource budgeting,
and safe autonomous execution without requiring user prompts.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable, Optional

from .decision_cycle import DecisionCycle
from .models import GoalStatus, PermissionTier, ProposedGoal, ReflectionRecord

logger = logging.getLogger("hinaa.agency.runtime")


class AgencyRuntime:
    """Singleton background orchestrator for Hina's independent agency."""

    def __init__(
        self,
        cycle_interval_seconds: int = 120,
        max_goals_per_hour: int = 10,
        workspace_root: Optional[str] = None,
        tool_executor: Optional[Callable[[str, dict[str, Any]], Any]] = None,
    ) -> None:
        self.cycle_interval_seconds = cycle_interval_seconds
        self.max_goals_per_hour = max_goals_per_hour
        self.is_paused = False
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._cycle = DecisionCycle(
            workspace_root=workspace_root,
            tool_executor=tool_executor,
        )
        self._recent_goals: deque[ProposedGoal] = deque(maxlen=100)
        self._reflections: deque[ReflectionRecord] = deque(maxlen=100)
        self._hour_timestamps: deque[float] = deque(maxlen=200)
        self._active_goal: Optional[ProposedGoal] = None
        self._total_cycles_run = 0
        self._heartbeat_daemon: Any = None

    def set_heartbeat_daemon(self, daemon: Any) -> None:
        self._heartbeat_daemon = daemon

    def pause(self) -> None:
        """Emergency pause switch for all autonomous background activity."""
        self.is_paused = True
        logger.info("Agency runtime paused by administrative command")

    def resume(self) -> None:
        """Resume autonomous background decision cycles."""
        self.is_paused = False
        logger.info("Agency runtime resumed")

    def start(self) -> None:
        """Start the autonomous background execution daemon."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="hinaa-agency-runtime")
        logger.info(
            "AgencyRuntime started (interval: %ds, max/hr: %d)",
            self.cycle_interval_seconds,
            self.max_goals_per_hour,
        )

    def stop(self) -> None:
        """Stop the autonomous daemon gracefully."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("AgencyRuntime stopped")

    def _can_execute_this_hour(self) -> bool:
        """Check rate-limit budget: enforce max_goals_per_hour."""
        now = time.time()
        # Evict timestamps older than 1 hour (3600s)
        while self._hour_timestamps and now - self._hour_timestamps[0] > 3600:
            self._hour_timestamps.popleft()
        return len(self._hour_timestamps) < self.max_goals_per_hour

    async def _run_loop(self) -> None:
        """Periodic background reasoning and execution loop."""
        # Initial boot delay to let server initialize
        await asyncio.sleep(5)

        while self._running:
            try:
                if not self.is_paused:
                    if self._can_execute_this_hour():
                        await self.trigger_cycle()
                    else:
                        logger.info("Agency hourly budget reached; sleeping until window rolls over.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Unhandled error in agency runtime loop: %s", e, exc_info=True)

            try:
                await asyncio.sleep(self.cycle_interval_seconds)
            except asyncio.CancelledError:
                break

    async def trigger_cycle(self) -> Optional[ProposedGoal]:
        """Trigger an immediate decision cycle (used by background loop or manual trigger)."""
        if self.is_paused:
            logger.info("Trigger skipped: Agency runtime is paused.")
            return None

        self._total_cycles_run += 1
        goal = await self._cycle.run_single_cycle()

        if goal:
            self._recent_goals.append(goal)
            self._hour_timestamps.append(time.time())
            if goal.reflection:
                self._reflections.append(goal.reflection)

            # Notify heartbeat daemon if attached
            if self._heartbeat_daemon and hasattr(self._heartbeat_daemon, "emit_pulse"):
                from ..intelligence.heartbeat import HeartbeatPulse
                pulse = HeartbeatPulse(
                    type="task_update",
                    title=f"Autonomous Goal: {goal.title}",
                    message=(
                        f"Hina independently completed '{goal.title}' with status {goal.status.value}. "
                        f"Category: {goal.category.value} | Utility Score: {goal.score}."
                    ),
                    action_type="view_task",
                    action_payload={"goal_id": goal.goal_id, "status": goal.status.value},
                )
                asyncio.create_task(self._heartbeat_daemon.emit_pulse(pulse))

        return goal

    def get_status(self) -> dict[str, Any]:
        """Fetch current operational status, active goals, and recent activity."""
        now = time.time()
        hourly_active = sum(1 for t in self._hour_timestamps if now - t <= 3600)

        return {
            "running": self._running,
            "paused": self.is_paused,
            "cycle_interval_seconds": self.cycle_interval_seconds,
            "max_goals_per_hour": self.max_goals_per_hour,
            "goals_run_last_hour": hourly_active,
            "budget_remaining": max(0, self.max_goals_per_hour - hourly_active),
            "total_cycles_run": self._total_cycles_run,
            "recent_goals": [g.model_dump() for g in reversed(list(self._recent_goals)[-10:])],
            "recent_reflections": [r.model_dump() for r in reversed(list(self._reflections)[-5:])],
        }


_GLOBAL_AGENCY_RUNTIME: Optional[AgencyRuntime] = None


def get_agency_runtime() -> AgencyRuntime:
    """Access the global AgencyRuntime singleton."""
    global _GLOBAL_AGENCY_RUNTIME
    if _GLOBAL_AGENCY_RUNTIME is None:
        _GLOBAL_AGENCY_RUNTIME = AgencyRuntime()
    return _GLOBAL_AGENCY_RUNTIME
