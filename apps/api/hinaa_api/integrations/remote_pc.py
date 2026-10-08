"""Short-lived PC grants created locally and bound to the verified owner."""
from __future__ import annotations
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import secrets
import threading
import time

@dataclass
class Grant:
    subject: str
    expires_at: float
    tools: frozenset[str]

class PCGrants:
    def __init__(self):
        self._grants: dict[str, Grant] = {}
        self._lock = threading.Lock()

    @staticmethod
    def key(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def issue(self, subject: str, tools: frozenset[str], minutes: int = 15):
        token = secrets.token_urlsafe(48)
        grant = Grant(subject, time.time() + min(max(minutes, 1), 15) * 60, tools)
        with self._lock:
            self._grants = {key: value for key, value in self._grants.items() if value.expires_at > time.time()}
            # One active session per owner; pairing again revokes the old session.
            self._grants = {key: value for key, value in self._grants.items() if value.subject != subject}
            self._grants[self.key(token)] = grant
        return token, grant.expires_at

    def allows(self, token: str, subject: str, tool: str) -> bool:
        with self._lock:
            grant = self._grants.get(self.key(token))
            return bool(grant and grant.subject == subject and grant.expires_at > time.time() and tool in grant.tools)

    def revoke(self, token: str, subject: str):
        with self._lock:
            key = self.key(token)
            grant = self._grants.get(key)
            if grant and grant.subject == subject:
                del self._grants[key]

pc_grants = PCGrants()
request_pc: ContextVar[tuple[str, str] | None] = ContextVar("request_pc", default=None)

def remote_tool_allowed(tool: str) -> bool:
    context = request_pc.get()
    return bool(context and pc_grants.allows(context[0], context[1], tool))
