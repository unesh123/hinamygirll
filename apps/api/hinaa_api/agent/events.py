from __future__ import annotations
from .contracts import AgentEvent


class EventLog:
    def __init__(self, run_id: str, conversation_id: str | None = None): self.run_id, self.conversation_id, self._events = run_id, conversation_id, []
    def emit(self, event_type: str, *, step_id: str | None = None, payload: dict | None = None) -> AgentEvent:
        event = AgentEvent(sequence=len(self._events) + 1, event_type=event_type, run_id=self.run_id, conversation_id=self.conversation_id, step_id=step_id, payload=payload or {})
        self._events.append(event); return event
    @property
    def events(self) -> list[AgentEvent]: return list(self._events)

