"""HINA ASTRA — Semantic Event Bus.

Handles asynchronous event publishing, buffering, and SSE streaming
for real-time backend-to-frontend synchronization.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from .types import AstraEvent


class AstraEventBus:
    """Asynchronous semantic event bus for a single Astra turn/session."""

    def __init__(self, request_id: str | None = None) -> None:
        self.request_id = request_id
        self._queue: asyncio.Queue[AstraEvent | None] = asyncio.Queue()
        self._events: list[AstraEvent] = []
        self._closed = False

    async def emit(self, event_type: str, data: dict[str, Any] | None = None) -> AstraEvent:
        """Publish a typed semantic event onto the stream."""
        payload = data or {}
        if self.request_id and "requestId" not in payload:
            payload["requestId"] = self.request_id

        event = AstraEvent(type=event_type, data=payload)
        self._events.append(event)
        if not self._closed:
            await self._queue.put(event)
        return event

    async def finish(self) -> None:
        """Close the event stream signal."""
        if not self._closed:
            self._closed = True
            await self._queue.put(None)

    async def stream_events(self) -> AsyncIterator[AstraEvent]:
        """Iterate over events as they arrive until finished."""
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event

    async def stream_sse(self) -> AsyncIterator[str]:
        """Format stream as text/event-stream payloads."""
        async for event in self.stream_events():
            yield event.to_sse()

    @property
    def history(self) -> list[AstraEvent]:
        """Return all historical events emitted in this session."""
        return list(self._events)
