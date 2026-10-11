"""Decides which origin the browser should open the realtime voice socket against.

Vercel's rewrites proxy HTTP but not WebSocket upgrades. So when the request
arrived through the public edge and no realtime origin is configured, the
request's own host cannot serve the socket. Advertising it sends voice to a
dead end; reporting "unavailable" lets the client say why.
"""
from __future__ import annotations

from dataclasses import dataclass

_SCHEME_PREFIXES = ("https://", "http://", "wss://", "ws://")


@dataclass(frozen=True)
class RealtimeOrigin:
    origin: str | None
    source: str


def _strip_scheme(value: str) -> str:
    text = value.lower()
    for prefix in _SCHEME_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.rstrip("/")


def choose_realtime_origin(*, configured: str, host: str, edge_request: bool) -> RealtimeOrigin:
    """Return the origin to advertise, or None when the socket cannot be reached."""
    if configured.strip():
        return RealtimeOrigin(_strip_scheme(configured), "configured")
    if edge_request:
        return RealtimeOrigin(None, "unavailable-edge")
    if host.strip():
        return RealtimeOrigin(_strip_scheme(host), "host")
    return RealtimeOrigin(None, "unavailable")
