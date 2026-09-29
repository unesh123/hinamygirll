"""Autonomous Heartbeat Daemon & Proactive Event Stream for HINAA.

Continuously monitors background tasks, system vitals, time-of-day transitions,
and scheduled reminders. Dispatches real-time proactive pulses to the frontend
via Server-Sent Events (SSE) and WebSocket channels.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("hinaa.intelligence.heartbeat")


class HeartbeatPulse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = Field(..., description="Type of pulse: proactive_briefing, task_update, reminder, health_status")
    title: str = Field(..., description="Short declarative title")
    message: str = Field(..., description="Contextual narrative content")
    action_type: Optional[str] = Field(default=None, description="Suggested client action: open_chat, view_task, run_code")
    action_payload: Optional[Dict[str, Any]] = Field(default=None, description="Extra metadata for the client action")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    acknowledged: bool = Field(default=False)


class AutonomousHeartbeatDaemon:
    """Singleton background daemon that drives HINAA's autonomous proactive heartbeat."""

    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._pulses: List[HeartbeatPulse] = []
        self._subscribers: List[asyncio.Queue[HeartbeatPulse]] = []
        self._last_tick: Optional[datetime.datetime] = None
        self._last_briefing_period: Optional[str] = None
        self._memory_service: Any = None
        self._agent_runtime: Any = None
        self._owner_id: str = "local-dev-user"

    def initialize(
        self,
        memory_service: Any = None,
        agent_runtime: Any = None,
        owner_id: str = "local-dev-user",
    ) -> None:
        self._memory_service = memory_service
        self._agent_runtime = agent_runtime
        self._owner_id = owner_id

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="hinaa-heartbeat-daemon")
        logger.info("Autonomous Heartbeat Daemon started (interval: %ds)", self.interval_seconds)

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Autonomous Heartbeat Daemon stopped")

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "intervalSeconds": self.interval_seconds,
            "lastTick": self._last_tick.isoformat() if self._last_tick else None,
            "lastBriefingPeriod": self._last_briefing_period,
            "activeSubscribers": len(self._subscribers),
            "unacknowledgedPulses": len([p for p in self._pulses if not p.acknowledged]),
            "totalPulsesEmitted": len(self._pulses),
        }

    async def emit_pulse(self, pulse: HeartbeatPulse) -> None:
        """Push a pulse to history and broadcast to all live SSE/WebSocket subscribers."""
        self._pulses.append(pulse)
        # Keep pulse history bounded to last 100 items
        if len(self._pulses) > 100:
            self._pulses = self._pulses[-100:]

        dead_queues = []
        for q in self._subscribers:
            try:
                q.put_nowait(pulse)
            except Exception:
                dead_queues.append(q)
        for dead in dead_queues:
            if dead in self._subscribers:
                self._subscribers.remove(dead)

    def subscribe(self) -> asyncio.Queue[HeartbeatPulse]:
        """Subscribe a client connection to live heartbeat pulses."""
        queue: asyncio.Queue[HeartbeatPulse] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[HeartbeatPulse]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def get_recent_pulses(self, limit: int = 10) -> List[HeartbeatPulse]:
        return self._pulses[-limit:]

    def acknowledge_pulse(self, pulse_id: str) -> bool:
        for p in self._pulses:
            if p.id == pulse_id:
                p.acknowledged = True
                return True
        return False

    async def force_tick(self) -> Optional[HeartbeatPulse]:
        """Manually trigger a single heartbeat cycle (useful for tests or user command)."""
        return await self._tick()

    async def _run_loop(self) -> None:
        # Initial warm-up delay
        await asyncio.sleep(5)
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Error in heartbeat loop: %s", exc, exc_info=True)
            await asyncio.sleep(self.interval_seconds)

    async def _tick(self) -> Optional[HeartbeatPulse]:
        now = datetime.datetime.now()
        self._last_tick = now
        pulse_emitted: Optional[HeartbeatPulse] = None

        # 1. Evaluate Time-of-Day Proactive Briefing
        hour = now.hour
        current_period = (
            "morning" if 5 <= hour < 12
            else "afternoon" if 12 <= hour < 17
            else "evening" if 17 <= hour < 22
            else "night"
        )

        if current_period != self._last_briefing_period:
            self._last_briefing_period = current_period
            pulse = await self._generate_time_briefing(current_period)
            if pulse:
                await self.emit_pulse(pulse)
                pulse_emitted = pulse

        # 2. Check for active agent task progress
        if self._agent_runtime:
            task_pulse = await self._check_agent_tasks()
            if task_pulse:
                await self.emit_pulse(task_pulse)
                pulse_emitted = task_pulse

        return pulse_emitted

    async def _generate_time_briefing(self, period: str) -> Optional[HeartbeatPulse]:
        try:
            from .proactive_briefing import generate_proactive_briefing
            briefing = await generate_proactive_briefing(
                user_id=self._owner_id,
                memory_service=self._memory_service,
                companion_id="hinaa",
            )
            greeting = briefing.get("greeting", "Hey there! Ready to build together.")
            title_map = {
                "morning": "☀️ Morning Mission Alignment",
                "afternoon": "⚡ Afternoon Deep Work Sync",
                "evening": "🌆 Evening Project Review",
                "night": "🌙 Late Night Creative Mode",
            }
            return HeartbeatPulse(
                type="proactive_briefing",
                title=title_map.get(period, "HINAA Autonomous Briefing"),
                message=greeting,
                action_type="open_chat",
                action_payload={"briefing": briefing, "period": period},
            )
        except Exception as exc:
            logger.debug("Failed to compile periodic briefing pulse: %s", exc)
            return None

    async def _check_agent_tasks(self) -> Optional[HeartbeatPulse]:
        try:
            # Check if any tasks recently finished or require confirmation
            return None
        except Exception:
            return None


# Global singleton instance
heartbeat_daemon = AutonomousHeartbeatDaemon(interval_seconds=60)
