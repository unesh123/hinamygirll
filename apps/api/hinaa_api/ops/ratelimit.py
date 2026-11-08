"""In-process token-bucket rate limiter (per worker)."""
from __future__ import annotations

import ipaddress
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

# POST routes that fan out to paid providers or heavy compute. Matched after
# stripping the optional "/api" prefix and trailing slash.
EXPENSIVE_POST_PATHS = frozenset(
    {
        "/v1/conversations/turns:stream",
        "/v1/astra/turns:stream",
        "/v1/creative/jobs",
        "/creative/jobs",
        "/v1/vision/react",
        "/v1/vision/observe",
        "/v1/telephony/calls",
        "/v1/mcp/tools/call",
        "/v1/browser/tasks",
        "/browser/tasks",
        "/v1/coding/tasks",
        "/coding/tasks",
        "/v1/speech/transcriptions",
    }
)

EXEMPT_PATHS = frozenset(
    {"/metrics", "/health", "/healthz", "/readyz", "/health/live", "/health/ready", "/api/health"}
)


def is_expensive(method: str, path: str) -> bool:
    if method != "POST":
        return False
    normalized = path.rstrip("/")
    if normalized.startswith("/api/"):
        normalized = normalized[4:]
    return normalized in EXPENSIVE_POST_PATHS


@dataclass
class Decision:
    allowed: bool
    retry_after: int = 0


class TokenBucketLimiter:
    def __init__(self, max_keys: int = 10_000, clock: Callable[[], float] = time.monotonic) -> None:
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()
        self._max_keys = max_keys
        self._clock = clock

    def check(self, key: str, per_minute: int) -> Decision:
        if per_minute <= 0:
            return Decision(True)
        rate = per_minute / 60.0
        now = self._clock()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(per_minute), now))
            tokens = min(float(per_minute), tokens + (now - last) * rate)
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                decision = Decision(True)
            else:
                self._buckets[key] = (tokens, now)
                decision = Decision(False, max(1, int((1.0 - tokens) / rate) + 1))
            if len(self._buckets) > self._max_keys:
                self._prune(now)
        return decision

    def _prune(self, now: float) -> None:
        # Idle for over a minute means the bucket is full again; dropping it is lossless.
        for key in [k for k, (_, last) in self._buckets.items() if now - last > 60]:
            del self._buckets[key]


def client_ip(scope_client: tuple[str, int] | None, forwarded_for: str | None, trust_proxy: bool) -> str:
    if trust_proxy and forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        try:
            return str(ipaddress.ip_address(first))
        except ValueError:
            pass
    return scope_client[0] if scope_client else "unknown"
