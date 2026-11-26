"""HINAA OS — Loop event bus for live SSE streaming.

A tiny process-local pub/sub: the loop agent step and the loop router publish
turn events; the SSE endpoint in ``loop_router`` streams them to the UI as
``text/event-stream``. Events are also kept in a bounded per-task history so a
client that connects mid-run can replay from the beginning or a sequence.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

_HISTORY_LIMIT = 500
_SUBSCRIBER_QUEUE_LIMIT = 256


class LoopEventBus:
    def __init__(self) -> None:
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        self._subscribers: Dict[str, List[_asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None:
        event = {
            "sequence": 0,
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "data": data,
        }
        async with self._lock:
            history = self._history.setdefault(task_id, [])
            event["sequence"] = (history[-1]["sequence"] + 1) if history else 1
            history.append(event)
            if len(history) > _HISTORY_LIMIT:
                del history[:-_HISTORY_LIMIT]
            for queue in list(self._subscribers.get(task_id, [])):
                if queue.full():
                    continue
                queue.put_nowait(event)

    def publish_sync(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None:
        """Publish from sync code (the executor runs actions synchronously)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            event = {
                "sequence": 0,
                "ts": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "data": data,
            }
            history = self._history.setdefault(task_id, [])
            event["sequence"] = (history[-1]["sequence"] + 1) if history else 1
            history.append(event)
            return
        loop.create_task(self.publish(task_id, event_type, data))

    def history(self, task_id: str, since_sequence: int = 0) -> List[Dict[str, Any]]:
        return [e for e in self._history.get(task_id, []) if e["sequence"] > since_sequence]

    async def subscribe(self, task_id: str, since_sequence: int = 0) -> "_asyncio.Queue":
        queue: _asyncio.Queue = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_LIMIT)
        async with self._lock:
            for event in self.history(task_id, since_sequence):
                queue.put_nowait(event)
            self._subscribers.setdefault(task_id, []).append(queue)
        return queue

    async def unsubscribe(self, task_id: str, queue: "_asyncio.Queue") -> None:
        async with self._lock:
            subscribers = self._subscribers.get(task_id, [])
            if queue in subscribers:
                subscribers.remove(queue)


EVENT_BUS = LoopEventBus()


def sse_format(event: Dict[str, Any]) -> str:
    payload = json.dumps(
        {"ts": event["ts"], "event_type": event["event_type"], "data": event["data"]},
        ensure_ascii=False,
        default=str,
    )
    return f"id: {event['sequence']}\nevent: {event['event_type']}\ndata: {payload}\n\n"


async def sse_stream(task_id: str, since_sequence: int = 0, idle_timeout_seconds: float = 30.0):
    """Yield SSE frames for a loop task; ends after the loop finishes."""
    queue = await EVENT_BUS.subscribe(task_id, since_sequence=since_sequence)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=idle_timeout_seconds)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield sse_format(event)
            if event["event_type"] in {"loop_finished", "loop_failed", "loop_paused", "loop_cancelled"}:
                yield "event: end\ndata: [DONE]\n\n"
                return
    finally:
        await EVENT_BUS.unsubscribe(task_id, queue)
