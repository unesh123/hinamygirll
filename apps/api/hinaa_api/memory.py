from __future__ import annotations

from collections import OrderedDict, deque


class SessionMemory:
    def __init__(self, session_limit: int, turn_limit: int) -> None:
        self._sessions: OrderedDict[str, deque[tuple[str, str]]] = OrderedDict()
        self._session_limit = session_limit
        self._turn_limit = turn_limit * 2

    def context(self, session_id: str) -> tuple[tuple[str, str], ...]:
        entries = self._sessions.get(session_id)
        if entries is None:
            return ()
        self._sessions.move_to_end(session_id)
        return tuple(entries)

    def append_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        entries = self._sessions.setdefault(session_id, deque(maxlen=self._turn_limit))
        entries.extend((("user", user_text), ("assistant", assistant_text)))
        self._sessions.move_to_end(session_id)
        while len(self._sessions) > self._session_limit:
            self._sessions.popitem(last=False)

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
