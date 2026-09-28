"""Graceful voice fallback decisions for Hina.

Her voice is an identity, but a voice that cannot speak is worse than a
different one that can. When the primary vendor (ElevenLabs) refuses a request
because the account is out of characters, the credential is rejected, or the
socket times out, she still owes the owner an audible reply. These helpers choose
the fallback voice, classify the failure, and remember a hard refusal for a short
window so the *next* turn does not pay the same vendor timeout again.

They are deliberately pure (no network, no I/O) so the policy is unit-testable.
"""

from __future__ import annotations

import time
from typing import Any

# Deepgram Aura female voice, verified to answer on the owner's account. Aura is
# English-first: the fallback is a graceful degradation for English replies, not
# a replacement for the ElevenLabs Hindi/Nepali sweet voice.
DEFAULT_HINAA_FALLBACK_VOICE = "aura-2-thalia-en"

# Statuses another vendor can actually cure. A rejected *parameter* (a model or
# voice the vendor will not honour) is not in this set on purpose: replaying it
# on a second vendor would just fail twice for the same reason.
_FALLBACK_STATUSES = frozenset(
    {"quotaFailed", "unavailable", "authenticationFailed", "timeout"}
)

# How long a hard vendor refusal suppresses the primary voice. Measured against
# the live account: a fresh attempt after a long refusal costs ~5s of vendor
# timeout plus retry backoff before the fallback even starts, which the owner
# hears as "her voice is broken". Ten minutes is long enough to stop that
# stutter on a burst of turns and short enough to pick up a topped-up account
# without a restart.
_COOLDOWN_SECONDS = 600.0
_cooldowns: dict[str, float] = {}


def fallback_voice_id(companion_id: str, *, hinaa_voice: str, hiro_voice: str) -> str:
    """Which Aura voice speaks for this companion."""
    return hiro_voice if companion_id == "hiro" else hinaa_voice


def status_of(error: Any) -> str | None:
    """The ElevenLabs status enum value carried by an error, if any."""
    status = getattr(error, "el_status", None)
    value = getattr(status, "value", None)
    return value if isinstance(value, str) else None


def is_fallback_worthy(error: Exception) -> bool:
    """True when a *different* vendor could plausibly answer.

    An error without an ElevenLabs status (a raw transport error, a timeout
    wrapper) is treated as fallback-worthy; a specific reject status is only
    worthy when another vendor could cure it.
    """
    if not hasattr(error, "el_status"):
        return True
    return status_of(error) in _FALLBACK_STATUSES


def note_voice_failure(provider: str, error: Exception, *, now: float | None = None) -> None:
    """Remember a vendor refusal so the next turn skips straight to the fallback.

    Only a classified vendor refusal starts a cooldown; a raw transport blip is
    not proof the account is down, so it is not remembered here.
    """
    if status_of(error) is None:
        return
    _cooldowns[provider] = (now if now is not None else time.time()) + _COOLDOWN_SECONDS


def voice_on_cooldown(provider: str, *, now: float | None = None) -> bool:
    """True while the primary voice is being skipped after a hard refusal."""
    until = _cooldowns.get(provider)
    if until is None:
        return False
    return (now if now is not None else time.time()) < until


def clear_voice_cooldown(provider: str | None = None) -> None:
    """Forget cooldowns (used by tests and by a manual provider refresh)."""
    if provider is None:
        _cooldowns.clear()
    else:
        _cooldowns.pop(provider, None)
