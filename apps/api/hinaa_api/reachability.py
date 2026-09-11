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
    "ThreeStageHealthOutcome",
    "is_ephemeral_tunnel",
    "probe_gateway",
    "probe_gateway_3stage",
    "reset_probe_cache",
    "reset_inference_cache",
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


@dataclass(frozen=True)
class ThreeStageHealthOutcome:
    configured: bool
    reachable: bool
    inference: bool
    state: str  # "healthy", "degraded", "rate_limited", "unavailable"
    latency_ms: int
    user_message: str
    retry_after_seconds: float = 0.0


_inference_cache: dict[str, tuple[float, ThreeStageHealthOutcome]] = {}


def reset_inference_cache() -> None:
    """Clear cached inference probe results."""
    _inference_cache.clear()


async def probe_gateway_3stage(
    base_url: str | None,
    api_key: str | None,
    model: str,
    provider_id: str = "cx-gateway",
    label: str = "CX Gateway",
    *,
    timeout: float = 20.0,
    allow_cached_fast: bool = True,
) -> ThreeStageHealthOutcome:
    """3-stage health check: CONFIG -> REACHABILITY -> INFERENCE."""
    # Stage 1: Config
    if not base_url or not api_key:
        return ThreeStageHealthOutcome(
            configured=False,
            reachable=False,
            inference=False,
            state="unavailable",
            latency_ms=0,
            user_message=f"{label} requires both base URL and API key to be configured.",
        )

    # Circuit breaker check: fail-fast if already in cooldown
    from .circuit_breaker import CircuitBreakerState, get_circuit_breaker

    breaker = get_circuit_breaker(provider_id)
    can_exec, breaker_reason, remaining_cooldown = breaker.can_execute()

    if not can_exec:
        state_map = {
            CircuitBreakerState.RATE_LIMITED: "rate_limited",
            CircuitBreakerState.AUTH_ERROR: "unavailable",
            CircuitBreakerState.CIRCUIT_OPEN: "unavailable",
            CircuitBreakerState.MODEL_UNAVAILABLE: "unavailable",
            CircuitBreakerState.TIMEOUT: "unavailable",
            CircuitBreakerState.OFFLINE: "unavailable",
            CircuitBreakerState.ENDPOINT_MISMATCH: "unavailable",
        }
        mapped_state = state_map.get(breaker.state, "unavailable")
        msg = breaker_reason or f"{label} is currently in {breaker.state.value} cooldown."
        return ThreeStageHealthOutcome(
            configured=True,
            reachable=True,
            inference=False,
            state=mapped_state,
            latency_ms=breaker.last_latency_ms,
            user_message=msg,
            retry_after_seconds=remaining_cooldown,
        )

    # Stage 2: Reachability
    reach_outcome = await probe_gateway(base_url)
    if not reach_outcome.reachable:
        breaker.record_failure("OFFLINE", reach_outcome.detail)
        return ThreeStageHealthOutcome(
            configured=True,
            reachable=False,
            inference=False,
            state="unavailable",
            latency_ms=0,
            user_message=f"{label} is configured but unreachable. {reach_outcome.detail}",
        )

    # Stage 3: Minimal Live Inference Probe with cache
    cache_key = f"{provider_id}:{model}"
    cached = _inference_cache.get(cache_key)
    if cached is not None:
        expires_at, outcome = cached
        now = monotonic()
        if now < expires_at or allow_cached_fast:
            if now >= expires_at:
                try:
                    asyncio.create_task(
                        probe_gateway_3stage(
                            base_url,
                            api_key,
                            model,
                            provider_id,
                            label=label,
                            timeout=timeout,
                            allow_cached_fast=False,
                        )
                    )
                except Exception:
                    pass
            return outcome

    started = monotonic()
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/chat/completions"):
        chat_url = cleaned
    elif cleaned.endswith("/v1"):
        chat_url = f"{cleaned}/chat/completions"
    else:
        chat_url = f"{cleaned}/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    model_for_probe = (
        model[3:] if (provider_id == "cx-gateway" and model.startswith("cx/")) else model
    )
    payload = {
        "model": model_for_probe,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }

    try:
        import httpx

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(chat_url, headers=headers, json=payload)
            latency_ms = int((monotonic() - started) * 1000)

            if resp.status_code == 200:
                breaker.record_success(latency_ms)
                outcome = ThreeStageHealthOutcome(
                    configured=True,
                    reachable=True,
                    inference=True,
                    state="healthy" if latency_ms < 4500 else "degraded",
                    latency_ms=latency_ms,
                    user_message=f"{label} ({model}) verified live ({latency_ms}ms).",
                )
                _inference_cache[cache_key] = (monotonic() + 300.0, outcome)
                return outcome

            if resp.status_code == 404:
                resp_text = resp.text.lower()
                if "model" in resp_text:
                    msg = f"{label} model '{model}' not found on endpoint."
                    breaker.record_failure("MODEL_UNAVAILABLE", msg)
                else:
                    msg = f"{label} endpoint mismatch (HTTP 404): verify base URL and route path."
                    breaker.record_failure("ENDPOINT_MISMATCH", msg)
                outcome = ThreeStageHealthOutcome(
                    configured=True,
                    reachable=True,
                    inference=False,
                    state="unavailable",
                    latency_ms=latency_ms,
                    user_message=msg,
                )
                _inference_cache[cache_key] = (monotonic() + 30.0, outcome)
                return outcome

            if resp.status_code == 429:
                retry_after_str = resp.headers.get("retry-after")
                retry_after = (
                    float(retry_after_str)
                    if retry_after_str and retry_after_str.strip().isdigit()
                    else 15.0
                )
                msg = f"{label} is rate limited right now ({int(retry_after)}s cooldown active)."
                breaker.record_failure("PROVIDER_RATE_LIMIT", msg, retry_after=retry_after)
                outcome = ThreeStageHealthOutcome(
                    configured=True,
                    reachable=True,
                    inference=False,
                    state="rate_limited",
                    latency_ms=latency_ms,
                    user_message=msg,
                    retry_after_seconds=retry_after,
                )
                _inference_cache[cache_key] = (monotonic() + 15.0, outcome)
                return outcome

            if resp.status_code in {401, 403}:
                msg = f"{label} credentials rejected (HTTP {resp.status_code})."
                breaker.record_failure("AUTH_ERROR", msg)
                outcome = ThreeStageHealthOutcome(
                    configured=True,
                    reachable=True,
                    inference=False,
                    state="unavailable",
                    latency_ms=latency_ms,
                    user_message=msg,
                )
                _inference_cache[cache_key] = (monotonic() + 60.0, outcome)
                return outcome

            resp_text = resp.text.lower()
            if any(m in resp_text for m in ("no available accounts", "no available account", "upstream account unavailable")):
                msg = f"{label} has no available upstream accounts."
                breaker.record_failure("PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE", msg)
                outcome = ThreeStageHealthOutcome(
                    configured=True,
                    reachable=True,
                    inference=False,
                    state="unavailable",
                    latency_ms=latency_ms,
                    user_message=msg,
                )
                _inference_cache[cache_key] = (monotonic() + 30.0, outcome)
                return outcome

            msg = f"{label} returned HTTP {resp.status_code}."
            breaker.record_failure("PROVIDER_UNAVAILABLE", msg)
            outcome = ThreeStageHealthOutcome(
                configured=True,
                reachable=True,
                inference=False,
                state="unavailable",
                latency_ms=latency_ms,
                user_message=msg,
            )
            _inference_cache[cache_key] = (monotonic() + 20.0, outcome)
            return outcome

    except Exception as exc:
        latency_ms = int((monotonic() - started) * 1000)
        msg = f"{label} probe error ({exc.__class__.__name__})."
        code = "PROVIDER_TIMEOUT" if "timeout" in msg.lower() else "PROVIDER_UNAVAILABLE"
        breaker.record_failure(code, msg)
        is_hard_failure = breaker.consecutive_failures >= breaker.failure_threshold
        outcome = ThreeStageHealthOutcome(
            configured=True,
            reachable=True,
            inference=False,
            state="unavailable" if is_hard_failure else "degraded",
            latency_ms=latency_ms,
            user_message=msg,
        )
        _inference_cache[cache_key] = (monotonic() + 15.0, outcome)
        return outcome
