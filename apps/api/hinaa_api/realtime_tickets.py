"""Single-use tickets that carry an authenticated identity to a WebSocket.

A browser cannot set an Authorization header on a WebSocket handshake, so the
realtime route cannot resolve a session token the way the HTTP routes do. The
client instead asks for a ticket over an authenticated HTTP request and sends
that ticket in the first WebSocket frame. The ticket is random, short lived and
consumed on first use, so it never appears in a URL where a proxy or an access
log would retain it.
"""

from __future__ import annotations

import secrets
import time

TICKET_TTL_SECONDS = 30
_MAX_LIVE_TICKETS = 512

_pending: dict[str, tuple[str, float]] = {}
_pc_pending: dict[str, tuple[str, str]] = {}


def _purge(now: float) -> None:
    for token in [t for t, (_, expires) in _pending.items() if expires <= now]:
        _pending.pop(token, None)
        _pc_pending.pop(token, None)


def issue(user_id: str, *, pc_context: tuple[str, str] | None = None) -> str:
    now = time.monotonic()
    _purge(now)
    while len(_pending) >= _MAX_LIVE_TICKETS:
        # Oldest-first eviction keeps a spammer from growing the table.
        oldest = next(iter(_pending))
        _pending.pop(oldest, None)
        _pc_pending.pop(oldest, None)
    token = secrets.token_urlsafe(24)
    _pending[token] = (user_id, now + TICKET_TTL_SECONDS)
    if pc_context:
        _pc_pending[token] = pc_context
    return token


def consume_bundle(token: str) -> tuple[str | None, tuple[str, str] | None]:
    entry = _pending.pop(token, None)
    pc_context = _pc_pending.pop(token, None)
    if entry is None:
        return None, None
    user_id, expires = entry
    if time.monotonic() > expires:
        return None, None
    return user_id, pc_context


def consume(token: str) -> str | None:
    """Spend a ticket and return only its authenticated owner."""
    return consume_bundle(token)[0]
