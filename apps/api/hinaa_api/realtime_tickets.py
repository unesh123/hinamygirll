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


def _purge(now: float) -> None:
    for token in [t for t, (_, expires) in _pending.items() if expires <= now]:
        _pending.pop(token, None)


def issue(user_id: str) -> str:
    now = time.monotonic()
    _purge(now)
    while len(_pending) >= _MAX_LIVE_TICKETS:
        # Oldest-first eviction keeps a spammer from growing the table.
        _pending.pop(next(iter(_pending)), None)
    token = secrets.token_urlsafe(24)
    _pending[token] = (user_id, now + TICKET_TTL_SECONDS)
    return token


def consume(token: str) -> str | None:
    """Return the owner of a ticket, or None. A ticket is spent either way."""
    entry = _pending.pop(token, None)
    if entry is None:
        return None
    user_id, expires = entry
    if time.monotonic() > expires:
        return None
    return user_id
