"""ActionGuard — the verify-after-every-action automation core.

The computer/browser/terminal tool contracts in this package all describe the
same loop::

    observe -> act -> observe -> verify -> recover / rollback -> repeat

but each tool was left to re-implement it (or skip it). ActionGuard is that
loop as one shared, deterministic, audit-ledgered engine:

- ``observe`` captures machine/browser/terminal state before and after action
- ``spec.predicate`` decides, from the *observed* state (never the model's
  belief), whether the action actually landed
- retries run an optional ``recover`` (cheap corrective step) before falling
  back to re-running the full action
- failure triggers an optional ``rollback(snapshot)`` so consequential
  operations stay reversible
- every run produces an :class:`ActionReceipt` and, when a ``RunLedger`` is
  provided, a durable audit receipt — no action is ever "done" because the
  model believed it finished.

Pure stdlib + the existing run ledger; no provider imports, so it is testable
in isolation and callable from any tool.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Literal

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..run_ledger import RunLedger

ActionFn = Callable[[], Awaitable[None]]
ObserveFn = Callable[[], Awaitable[Any]]
PredicateFn = Callable[[Any], bool]
RecoverFn = Callable[[Any], Awaitable[None]]
RollbackFn = Callable[[Any], Awaitable[None]]

ActionStatus = Literal["verified", "recovered", "failed"]


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded retry semantics for one guarded action."""

    max_attempts: int = 3
    backoff_seconds: float = 0.25
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be >= 0")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be >= 1")


@dataclass(frozen=True)
class VerificationSpec:
    """How to decide an action landed.

    ``description`` is a human-readable contract ("Antigravity opened the HINAA
    workspace") recorded on the receipt. ``predicate`` receives the *observed*
    post-action state and must return True only when the goal is verifiably
    reached. Deterministic checks preferred; model judges only when no
    deterministic check exists.
    """

    description: str
    predicate: PredicateFn
    observe_before: bool = True


@dataclass(frozen=True)
class ObservationRecord:
    attempt: int
    elapsed_ms: float
    passed: bool


@dataclass
class ActionReceipt:
    """Structured outcome of one guarded action — the unit of accountability."""

    receipt_id: str
    action_name: str
    status: ActionStatus
    attempts: int
    verified: bool
    duration_ms: float
    observations: list[ObservationRecord] = field(default_factory=list)
    error: str | None = None

    def as_metadata(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "action_name": self.action_name,
            "status": self.status,
            "attempts": self.attempts,
            "verified": self.verified,
            "duration_ms": round(self.duration_ms, 2),
            "observations": [
                {
                    "attempt": o.attempt,
                    "elapsed_ms": round(o.elapsed_ms, 2),
                    "passed": o.passed,
                }
                for o in self.observations
            ],
            "error": self.error,
        }


async def run_guarded_action(
    *,
    action_name: str,
    action: ActionFn,
    observe: ObserveFn,
    spec: VerificationSpec,
    policy: RetryPolicy | None = None,
    recover: RecoverFn | None = None,
    rollback: RollbackFn | None = None,
    ledger: "RunLedger | None" = None,
    turn_id: str = "action-guard",
    session_id: str | None = None,
) -> ActionReceipt:
    """Execute ``action`` and do not trust it until the world agrees.

    Flow: optional pre-observation snapshot -> act -> observe -> predicate.
    On mismatch: recover-then-reverify (if ``recover`` given) or re-act, with
    exponential backoff, up to ``policy.max_attempts``. If verification never
    passes, run ``rollback`` with the pre-action snapshot when provided and
    report ``failed``. Every outcome is receipted; a ledger write is attempted
    for both the action and its final verification.
    """
    policy = policy or RetryPolicy()
    started = time.perf_counter()
    receipt = ActionReceipt(
        receipt_id=f"ag_{uuid.uuid4().hex[:12]}",
        action_name=action_name,
        status="failed",
        attempts=0,
        verified=False,
        duration_ms=0.0,
    )

    snapshot: Any = None
    try:
        if spec.observe_before:
            snapshot = await observe()

        last_observation: Any = None
        last_error: str | None = None
        for attempt in range(1, policy.max_attempts + 1):
            receipt.attempts = attempt
            try:
                if attempt == 1 or recover is None:
                    await action()
                else:
                    # Recover is the cheap corrective path; it may itself fix
                    # state without replaying the whole (possibly expensive)
                    # action.
                    await recover(last_observation)

                last_observation = await observe()
            except Exception as exc:  # noqa: BLE001 - transient surfaces must retry
                last_error = f"{type(exc).__name__}: {exc}"
                receipt.observations.append(
                    ObservationRecord(
                        attempt=attempt,
                        elapsed_ms=(time.perf_counter() - started) * 1000.0,
                        passed=False,
                    )
                )
                if attempt < policy.max_attempts:
                    backoff = policy.backoff_seconds * (
                        policy.backoff_multiplier ** (attempt - 1)
                    )
                    if backoff > 0:
                        await asyncio.sleep(backoff)
                continue

            passed = bool(spec.predicate(last_observation))
            receipt.observations.append(
                ObservationRecord(
                    attempt=attempt,
                    elapsed_ms=(time.perf_counter() - started) * 1000.0,
                    passed=passed,
                )
            )
            if passed:
                receipt.status = "verified" if attempt == 1 else "recovered"
                receipt.verified = True
                break

            if attempt < policy.max_attempts:
                backoff = policy.backoff_seconds * (
                    policy.backoff_multiplier ** (attempt - 1)
                )
                if backoff > 0:
                    await asyncio.sleep(backoff)

        if not receipt.verified:
            receipt.error = receipt.error or last_error

        if not receipt.verified and rollback is not None and spec.observe_before:
            await rollback(snapshot)
    except Exception as exc:  # noqa: BLE001 - failures must become receipts
        receipt.status = "failed"
        receipt.error = f"{type(exc).__name__}: {exc}"
    finally:
        receipt.duration_ms = (time.perf_counter() - started) * 1000.0
        if ledger is not None and getattr(ledger, "available", False):
            ledger.record_receipt(
                turn_id=turn_id,
                session_id=session_id,
                step_type="action_guard",
                step_name=action_name,
                status=receipt.status,
                duration_ms=int(receipt.duration_ms),
                input_summary=spec.description,
                output_summary=(
                    f"verified={receipt.verified} attempts={receipt.attempts}"
                ),
                error=receipt.error,
                metadata=receipt.as_metadata(),
            )

    return receipt
