"""Live reachability probes for provider gateways.

Configuration presence is not availability. A provider hosted on an ephemeral
quick tunnel (``trycloudflare.com``, ``ngrok``, ``loca.lt``) keeps its key and
URL in the environment long after the tunnel process has exited, so a
config-only health check reports "ready" for an endpoint whose DNS name no
longer resolves. The user then selects that brain, sees a green "Ready" badge,
and every turn fails with PROVIDER_UNAVAILABLE.

This module answers the narrower, honest question: *can we currently open a
connection to this host?* It deliberately does not send a model request:

- No tokens are spent and no provider quota is consumed.
- An auth failure (401) or an empty account balance is **not** treated as
  unreachable, because those are different problems with different fixes.

Results are cached briefly so the providers endpoint stays fast when the UI
polls it.
"""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlsplit

__all__ = [
    "ProbeOutcome",
    "is_ephemeral_tunnel",
    "probe_gateway",
    "reset_probe_cache",
]

# Hosts whose URLs routinely outlive the process serving them. These are the
# providers where a config-only health check is actively misleading.
_EPHEMERAL_TUNNEL_SUFFIXES = (
    "trycloudflare.com",
    "ngrok.io",
    "ngrok-free.app",
    "ngrok.app",
    "loca.lt",
    "serveo.net",
    "localhost.run",
)

_PROBE_TIMEOUT_SECONDS = 2.0
_CACHE_TTL_SECONDS = 30.0
_FAILURE_CACHE_TTL_SECONDS = 10.0


@dataclass(frozen=True)
class ProbeOutcome:
    """Result of a connection-level reachability check."""

    reachable: bool
    """True when a TCP connection to the gateway host was established."""

    reason: str
    """Machine-readable outcome: ``ok``, ``dns_unresolved``, ``refused``,
    ``timeout``, ``error``, or ``no_host``."""

    detail: str
    """Short human-readable explanation suitable for a user-facing message."""


_cache: dict[str, tuple[float, ProbeOutcome]] = {}


def reset_probe_cache() -> None:
    """Clear cached probe results. Intended for tests and config reloads."""
    _cache.clear()


def is_ephemeral_tunnel(base_url: str | None) -> bool:
    """True when the URL is hosted on a tunnel that can disappear silently."""
    host = _host_of(base_url)
    if not host:
        return False
    return any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in _EPHEMERAL_TUNNEL_SUFFIXES
    )


def _host_of(base_url: str | None) -> str | None:
    if not base_url:
        return None
    raw = base_url.strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        return (urlsplit(raw).hostname or "").lower() or None
    except ValueError:
        return None


def _port_of(base_url: str | None) -> int:
    if not base_url:
        return 443
    raw = base_url.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        parts = urlsplit(raw)
    except ValueError:
        return 443
    if parts.port:
        return parts.port
    return 80 if parts.scheme == "http" else 443


async def probe_gateway(
    base_url: str | None,
    *,
    timeout: float = _PROBE_TIMEOUT_SECONDS,
    use_cache: bool = True,
) -> ProbeOutcome:
    """Check whether ``base_url`` currently accepts connections.

    Returns quickly and never raises. A dead quick tunnel fails DNS resolution,
    which is the fastest and least ambiguous signal that the endpoint is gone.
    """
    host = _host_of(base_url)
    if not host:
        return ProbeOutcome(False, "no_host", "No gateway URL is configured.")

    port = _port_of(base_url)
    key = f"{host}:{port}"

    if use_cache:
        cached = _cache.get(key)
        if cached is not None:
            expires_at, outcome = cached
            if monotonic() < expires_at:
                return outcome

    outcome = await _connect(host, port, timeout)

    ttl = _CACHE_TTL_SECONDS if outcome.reachable else _FAILURE_CACHE_TTL_SECONDS
    _cache[key] = (monotonic() + ttl, outcome)
    return outcome


async def _connect(host: str, port: int, timeout: float) -> ProbeOutcome:
    writer = None
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        return ProbeOutcome(True, "ok", "Gateway host is reachable.")
    except asyncio.TimeoutError:
        return ProbeOutcome(
            False,
            "timeout",
            f"Gateway host {host} did not respond within {timeout:g}s.",
        )
    except socket.gaierror:
        return ProbeOutcome(
            False,
            "dns_unresolved",
            f"Gateway host {host} no longer resolves — the tunnel has expired.",
        )
    except (ConnectionRefusedError, OSError) as exc:
        return ProbeOutcome(
            False,
            "refused",
            f"Gateway host {host} refused the connection ({exc.__class__.__name__}).",
        )
    except Exception as exc:  # pragma: no cover - defensive
        return ProbeOutcome(
            False,
            "error",
            f"Gateway host {host} could not be checked ({exc.__class__.__name__}).",
        )
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
