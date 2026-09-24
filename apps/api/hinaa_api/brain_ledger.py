"""What the last live call actually proved about each brain.

A health badge built from configuration answers "does this deployment hold a key?",
which outlives the truth: a gateway keeps its environment variables after its
credential starts returning HTTP 403, and the badge stays green while every turn
falls back to another brain. This module records the outcome of attempts that
really happened, and keeps them on disk so the verdict outlives the process that
measured it — this backend is a bare uvicorn that gets restarted by hand.

The ledger is written only from the turn path, so every record is a call the owner
paid for or waited on. Nothing here is a prediction.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

logger = logging.getLogger("hinaa.brain_ledger")

# An outcome describes a connection the deployment may no longer have. Keep the
# verdict long enough that every badge in a session agrees, and short enough that
# a brain auto-selection has stopped offering still gets re-tried instead of
# staying red on evidence nobody has re-checked. Expired evidence reports as
# untested — never as healthy.
LIVE_OUTCOME_WINDOW_SECONDS = 900.0

_DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "brain_outcomes.json"

# Intact brain, blocked this once: throttled or too slow, not broken. Every other
# failure (rejected key, retired model, dead endpoint) reports as unavailable.
TRANSIENT_CODES = frozenset({"PROVIDER_RATE_LIMIT", "PROVIDER_TIMEOUT"})
# A refusal is an answer. It says nothing about whether the brain can serve.
NON_INFRA_CODES = frozenset({"SAFETY_REFUSAL"})

# Brains that answer in-process need no network, so configuration does prove them.
LOCAL_BRAIN_PREFIXES = ("mock", "local")

_lock = threading.Lock()
_cache: dict[str, dict[str, Any]] | None = None


@dataclass(frozen=True)
class BrainVerdict:
    brain_id: str
    state: str
    message: str
    ok: bool
    code: str
    model: str
    age_seconds: float


def is_local_brain(brain_id: str) -> bool:
    return brain_id.startswith(LOCAL_BRAIN_PREFIXES)


def ledger_path() -> Path:
    override = os.environ.get("HINAA_BRAIN_LEDGER_PATH", "").strip()
    return Path(override) if override else _DEFAULT_PATH


def _read() -> dict[str, dict[str, Any]]:
    global _cache
    if _cache is not None:
        return _cache
    outcomes: dict[str, dict[str, Any]] = {}
    try:
        raw = json.loads(ledger_path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            outcomes = {k: v for k, v in raw.items() if isinstance(v, dict)}
    except FileNotFoundError:
        pass
    except Exception:  # a corrupt ledger must never break a status endpoint
        logger.warning("Brain ledger unreadable; starting empty", exc_info=True)
    _cache = outcomes
    return outcomes


def _write(outcomes: dict[str, dict[str, Any]]) -> None:
    global _cache
    _cache = outcomes
    path = ledger_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(outcomes, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:  # a badge is never worth failing a turn over
        logger.warning("Brain ledger unwritable", exc_info=True)


def record_call(
    brain_id: str,
    *,
    ok: bool,
    code: str = "",
    detail: str = "",
    model: str = "",
    fingerprint: str = "",
) -> None:
    """Store what one real attempt to one brain ended with."""
    if not brain_id or is_local_brain(brain_id):
        return
    if not ok and code in NON_INFRA_CODES:
        return
    with _lock:
        outcomes = dict(_read())
        outcomes[brain_id] = {
            "ok": bool(ok),
            "code": (code or "")[:60],
            "detail": (detail or "")[:300],
            "model": (model or "")[:100],
            "fingerprint": fingerprint,
            "at": time.time(),
        }
        _write(outcomes)


def _humanize(seconds: float) -> str:
    if seconds < 45:
        return "just now"
    if seconds < 5400:
        return f"{int(round(seconds / 60))} min ago"
    return f"{int(round(seconds / 3600))} h ago"


def _state_for(record: Mapping[str, Any]) -> str:
    if record.get("ok"):
        return "healthy"
    if str(record.get("code") or "") in TRANSIENT_CODES:
        return "degraded"
    return "unavailable"


def _verdict_from(brain_id: str, record: Mapping[str, Any], now: float) -> BrainVerdict:
    age = max(0.0, now - float(record.get("at") or 0.0))
    ok = bool(record.get("ok"))
    model = str(record.get("model") or "")
    state = _state_for(record)
    if ok:
        message = (
            f"{brain_id} answered the last live call"
            f"{f' with {model}' if model else ''} {_humanize(age)}."
        )
    elif state == "degraded":
        message = (
            f"{brain_id} was throttled or timed out on the last live call "
            f"{_humanize(age)}: {record.get('detail') or record.get('code')}"
        )
    else:
        message = (
            f"{brain_id} failed the last live call {_humanize(age)}: "
            f"{record.get('detail') or record.get('code') or 'no detail recorded'}"
        )
    return BrainVerdict(
        brain_id=brain_id,
        state=state,
        message=message,
        ok=ok,
        code=str(record.get("code") or ""),
        model=model,
        age_seconds=age,
    )


def newest_verdict(
    brain_ids: Sequence[str],
    *,
    fingerprints: Mapping[str, str] | None = None,
    window_seconds: float = LIVE_OUTCOME_WINDOW_SECONDS,
) -> BrainVerdict | None:
    """The most recent live evidence for any name this brain answers to.

    A verdict measured against different credentials or a different endpoint is
    dropped: that would punish a configuration the owner already fixed. Returning
    None means nobody has measured this brain, which is not the same as it working.
    """
    outcomes = _read()
    now = time.time()
    best: tuple[float, str, dict[str, Any]] | None = None
    for brain_id in brain_ids:
        record = outcomes.get(brain_id)
        if not record:
            continue
        expected = (fingerprints or {}).get(brain_id)
        # An expected identity is a demand, not a filter: a record written
        # without key material cannot be attributed to this connection at all.
        if expected and str(record.get("fingerprint") or "") != expected:
            continue
        at = float(record.get("at") or 0.0)
        if now - at > window_seconds:
            continue
        if best is None or at > best[0]:
            best = (at, brain_id, record)
    if best is None:
        return None
    return _verdict_from(best[1], best[2], now)


def newest_success(
    *,
    window_seconds: float = LIVE_OUTCOME_WINDOW_SECONDS,
) -> BrainVerdict | None:
    """Which brain most recently answered a real call, whoever that was.

    A row-scoped verdict can only answer "is this brain well?". `/health` needs the
    other question — who actually spoke last — because a deployment configured for
    one brain keeps reporting that name while a different one serves every turn.
    Success only: a failed attempt proves nobody answered.
    """
    outcomes = _read()
    now = time.time()
    best: tuple[float, str, dict[str, Any]] | None = None
    for brain_id, record in outcomes.items():
        if not record.get("ok"):
            continue
        at = float(record.get("at") or 0.0)
        if now - at > window_seconds:
            continue
        if best is None or at > best[0]:
            best = (at, brain_id, record)
    if best is None:
        return None
    return _verdict_from(best[1], best[2], now)


# Ledger names are the provider ids that actually ran; badge names are the rows of
# /v1/providers. They differ wherever one row fronts several client implementations.
_ROW_ALIASES: dict[str, tuple[str, ...]] = {
    "agent-router": ("agent-router", "agent-router-openai", "agent-router-anthropic"),
    "gemini": ("gemini", "real"),
}

# Provider row id -> the Settings field prefix holding its credential.
_SETTINGS_PREFIX: dict[str, str] = {
    "agent-router": "agent_router",
    "claude": "claude",
    "codecraft": "codecraft",
    "custom": "custom",
    "cx-gateway": "cx_gateway",
    "gemini": "gemini",
    "groq": "groq",
    "ollama": "ollama",
    "omniroute": "omniroute",
    "openai": "openai",
    "qwen": "qwen",
}


def aliases_for(row_id: str) -> tuple[str, ...]:
    return _ROW_ALIASES.get(row_id, (row_id,))


_BRAIN_ROW = {brain: row for row, brains in _ROW_ALIASES.items() for brain in brains}


def row_for_brain(brain_id: str) -> str:
    """Which badge row a brain that actually ran answers to."""
    return _BRAIN_ROW.get(brain_id, brain_id)


def _setting(settings: Any, *names: str) -> str:
    for name in names:
        value = getattr(settings, name, None)
        if value is None:
            continue
        secret = getattr(value, "get_secret_value", None)
        if callable(secret):
            value = secret()
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def fingerprint_for(settings: Any, row_id: str) -> str:
    """Identity of the connection a verdict was measured against.

    Key material is hashed, never stored: the ledger is read by a public endpoint.
    """
    prefix = _SETTINGS_PREFIX.get(row_id)
    if not prefix or settings is None:
        return ""
    key = _setting(settings, f"{prefix}_api_key", f"active_{prefix}_key")
    base = _setting(settings, f"active_{prefix}_base_url", f"{prefix}_base_url")
    model = _setting(settings, f"active_{prefix}_model", f"{prefix}_model")
    if not (key or base or model):
        return ""
    digest = hashlib.sha256(f"{key}|{base}|{model}".encode("utf-8")).hexdigest()
    return digest[:12]


def fingerprints_for(settings: Any, row_id: str) -> dict[str, str]:
    fingerprint = fingerprint_for(settings, row_id)
    return {brain_id: fingerprint for brain_id in aliases_for(row_id)}


def configured(settings: Any, row_id: str) -> bool:
    """Whether this row holds a credential, independent of any live call.

    Absence of evidence has two causes: the owner never configured the brain, or
    he did and nobody has asked it anything recently. Only the first is a fact the
    status endpoint can state without spending a request, so it is reported as
    "not configured" rather than as an untested badge.
    """
    prefix = _SETTINGS_PREFIX.get(row_id)
    if not prefix or settings is None:
        return bool(getattr(settings, f"{row_id}_configured", False))
    return bool(getattr(settings, f"{prefix}_configured", False))


def reset_ledger(path: str | Path | None = None) -> None:
    """Drop the in-process view (and optionally relocate the file) for tests."""
    global _cache
    if path is not None:
        os.environ["HINAA_BRAIN_LEDGER_PATH"] = str(path)
    _cache = None
