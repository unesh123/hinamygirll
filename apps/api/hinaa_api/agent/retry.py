from __future__ import annotations
from enum import Enum


class FailureCategory(str, Enum):
    VALIDATION_ERROR="validation_error"; AUTHORIZATION_ERROR="authorization_error"; CONFIRMATION_REQUIRED="confirmation_required"; FORBIDDEN_CAPABILITY="forbidden_capability"; TIMEOUT="timeout"; PROVIDER_UNAVAILABLE="provider_unavailable"; RATE_LIMITED="rate_limited"; TRANSIENT_NETWORK_ERROR="transient_network_error"; TOOL_EXECUTION_ERROR="tool_execution_error"; CANCELLED="cancelled"; INTERNAL_ERROR="internal_error"


RETRYABLE = {FailureCategory.TIMEOUT, FailureCategory.PROVIDER_UNAVAILABLE, FailureCategory.RATE_LIMITED, FailureCategory.TRANSIENT_NETWORK_ERROR}

# HinaaError is a dataclass Exception, so its args stay empty and str(err) is
# "". Matching on str() meant a mapped provider failure — including the
# connection resets the agent-router gateway throws — was never retried.
_RETRYABLE_HINTS = (
    "timeout",
    "rate_limit",
    "rate limited",
    "transient",
    "network",
    "unavailable",
    "unreachable",
    "connection",
    "reset by peer",
    "temporarily unavail",
)


def _retryable_haystack(item: Exception) -> str:
    parts = [
        str(getattr(item, name, "") or "")
        for name in ("code", "message", "developer_message")
    ]
    return " ".join(parts).strip() or str(item)


def is_retryable(item: FailureCategory | Exception | str) -> bool:
    if isinstance(item, FailureCategory):
        return item in RETRYABLE
    if isinstance(item, Exception):
        msg = _retryable_haystack(item).lower()
        return any(w in msg for w in _RETRYABLE_HINTS)
    if isinstance(item, str):
        try:
            return FailureCategory(item) in RETRYABLE
        except ValueError:
            return any(w in item.lower() for w in _RETRYABLE_HINTS)
    return False

