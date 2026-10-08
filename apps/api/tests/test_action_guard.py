"""ActionGuard — real integration tests for the verify-after-action loop.

These tests execute the actual guard engine: stateful fake machines stand in
for a browser/desktop surface, and every behavior asserted here is a real
execution of observe -> act -> verify -> recover/rollback, not a mock of the
guard itself.
"""

from __future__ import annotations

import asyncio

from hinaa_api.run_ledger import RunLedger
from hinaa_api.tools.action_guard import (
    RetryPolicy,
    VerificationSpec,
    run_guarded_action,
)


class FakeMachine:
    """Minimal stand-in for a controllable surface (browser tab, app window...)."""

    def __init__(self) -> None:
        self.opened = False
        self.fail_next_action = 0  # N next actions throw (transient outage)
        self.recover_calls = 0
        self.rollback_calls = 0

    async def act_open(self) -> None:
        if self.fail_next_action > 0:
            self.fail_next_action -= 1
            raise ConnectionError("surface unreachable")
        self.opened = True

    async def observe(self) -> dict:
        return {"opened": self.opened}

    async def recover(self, _obs: dict) -> None:
        self.recover_calls += 1
        self.opened = True

    async def rollback(self, snapshot: dict) -> None:
        self.rollback_calls += 1
        self.opened = bool(snapshot.get("opened", False))


def run(coro):
    return asyncio.run(coro)


def test_verified_first_attempt_when_action_lands():
    machine = FakeMachine()
    receipt = run(
        run_guarded_action(
            action_name="open_app",
            action=machine.act_open,
            observe=machine.observe,
            spec=VerificationSpec(
                description="app reports itself open",
                predicate=lambda obs: obs["opened"] is True,
            ),
        )
    )
    assert receipt.status == "verified"
    assert receipt.verified is True
    assert receipt.attempts == 1
    assert len(receipt.observations) == 1
    assert receipt.observations[0].passed is True


def test_recovered_via_recover_step_without_replaying_action():
    machine = FakeMachine()
    receipt = run(
        run_guarded_action(
            action_name="fix_state",
            # Action alone never flips the flag; recover does.
            action=lambda: asyncio.sleep(0),
            observe=machine.observe,
            spec=VerificationSpec(
                description="surface in target state",
                predicate=lambda obs: obs["opened"] is True,
            ),
            policy=RetryPolicy(max_attempts=3, backoff_seconds=0),
            recover=machine.recover,
        )
    )
    assert receipt.status == "recovered"
    assert receipt.verified is True
    assert receipt.attempts == 2
    assert machine.recover_calls == 1


def test_retries_transient_action_failure_then_verifies():
    machine = FakeMachine()
    machine.fail_next_action = 1  # first act() raises, retry succeeds
    receipt = run(
        run_guarded_action(
            action_name="open_app_flaky",
            action=machine.act_open,
            observe=machine.observe,
            spec=VerificationSpec(
                description="app open after transient failure",
                predicate=lambda obs: obs["opened"] is True,
            ),
            policy=RetryPolicy(max_attempts=3, backoff_seconds=0),
        )
    )
    assert receipt.verified is True
    assert receipt.attempts == 2
    assert receipt.error is None


def test_failed_runs_rollback_with_pre_action_snapshot():
    machine = FakeMachine()
    machine.opened = True  # pre-existing state that must be preserved
    receipt = run(
        run_guarded_action(
            action_name="impossible_mutation",
            action=lambda: asyncio.sleep(0),  # never changes anything
            observe=machine.observe,
            spec=VerificationSpec(
                description="state flipped to impossible target",
                predicate=lambda obs: obs["opened"] is False,
            ),
            policy=RetryPolicy(max_attempts=2, backoff_seconds=0),
            rollback=machine.rollback,
        )
    )
    assert receipt.status == "failed"
    assert receipt.verified is False
    assert receipt.attempts == 2
    assert machine.rollback_calls == 1
    assert machine.opened is True  # rolled back to the snapshot


def test_action_exception_becomes_failed_receipt_not_raise():
    machine = FakeMachine()

    async def exploding() -> None:
        raise RuntimeError("UIA tree vanished")

    receipt = run(
        run_guarded_action(
            action_name="explode",
            action=exploding,
            observe=machine.observe,
            spec=VerificationSpec(
                description="never reached",
                predicate=lambda obs: obs["opened"] is True,
            ),
            policy=RetryPolicy(max_attempts=2, backoff_seconds=0),
        )
    )
    assert receipt.status == "failed"
    assert "UIA tree vanished" in (receipt.error or "")


def test_receipt_is_written_to_run_ledger(tmp_path):
    ledger = RunLedger(tmp_path / "ledger.db")
    machine = FakeMachine()
    receipt = run(
        run_guarded_action(
            action_name="ledgered_open",
            action=machine.act_open,
            observe=machine.observe,
            spec=VerificationSpec(
                description="app open, receipt durable",
                predicate=lambda obs: obs["opened"] is True,
            ),
            ledger=ledger,
            turn_id="test-turn-1",
        )
    )
    rows = ledger.recent_receipts(turn_id="test-turn-1", limit=5)
    assert receipt.verified is True
    assert len(rows) == 1
    assert rows[0]["stepType"] == "action_guard"
    assert rows[0]["stepName"] == "ledgered_open"
    assert rows[0]["status"] == "verified"
    assert rows[0]["metadata"]["verified"] is True
    ledger.close()


def test_retry_policy_validates_bounds():
    import pytest

    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(backoff_seconds=-1)
    with pytest.raises(ValueError):
        RetryPolicy(backoff_multiplier=0.5)
