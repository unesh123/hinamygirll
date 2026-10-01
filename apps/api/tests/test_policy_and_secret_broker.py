"""
Test Suite for Policy-as-Code Engine and Secret Broker.
"""

import pytest
import time
from hinaa_api.security.policy_engine import (
    PolicyEngine,
    PolicyDecisionType,
)
from hinaa_api.security.secret_broker import (
    SecretBroker,
    get_secret_broker,
)


def test_policy_pre_check_denial():
    engine = PolicyEngine()
    res = engine.evaluate_pre_policy(
        actor="user:123",
        resource="terminal",
        action="rm_rf_root",
        arguments={"cmd": "rm -rf /"},
        run_id="run_test_1",
    )
    assert res.decision == PolicyDecisionType.DENY
    assert "strictly forbidden" in res.reason


def test_policy_approval_challenge_and_recheck_lifecycle():
    engine = PolicyEngine()
    args = {"recipient": "Team", "text": "Deploy to production"}

    # 1. Pre-policy triggers approval requirement
    pre = engine.evaluate_pre_policy(
        actor="user:123",
        resource="production",
        action="deploy",
        arguments=args,
        run_id="run_test_2",
    )
    assert pre.decision == PolicyDecisionType.REQUIRE_APPROVAL
    assert pre.challenge is not None
    challenge = pre.challenge

    # 2. Re-check authorizes valid challenge
    ok, msg = engine.recheck_and_authorize(challenge, actor="user:123", arguments=args)
    assert ok is True
    assert "Authorized" in msg

    # 3. Anti-replay: challenge cannot be used a second time
    replay_ok, replay_msg = engine.recheck_and_authorize(challenge, actor="user:123", arguments=args)
    assert replay_ok is False
    assert "already been used" in replay_msg


def test_policy_detects_argument_tampering():
    engine = PolicyEngine()
    args = {"recipient": "Team", "text": "Harmless message"}

    pre = engine.evaluate_pre_policy(
        actor="user:123",
        resource="whatsapp",
        action="send_message",
        arguments=args,
        run_id="run_test_3",
    )
    challenge = pre.challenge
    assert challenge is not None

    # Attacker alters arguments before execution
    tampered_args = {"recipient": "Team", "text": "MALICIOUS PAYLOAD"}
    ok, msg = engine.recheck_and_authorize(challenge, actor="user:123", arguments=tampered_args)
    assert ok is False
    assert "altered" in msg.lower()


def test_secret_broker_zero_leak_and_scrubbing():
    broker = SecretBroker()
    raw_key = "sk_live_enterprise_prod_9981247"
    broker.store_secret("openai_prod", raw_key)

    # 1. Issues opaque handle without revealing raw secret
    handle = broker.issue_capability_handle("openai_prod", ttl_seconds=60)
    assert handle.handle_id.startswith("cap_hina_")
    assert raw_key not in handle.handle_id

    # 2. Resolves inside executor
    resolved = broker.resolve_handle_for_executor(handle.handle_id)
    assert resolved == raw_key

    # 3. Proactive text scrubbing
    log_sample = f"Calling API with {raw_key} at endpoint https://api.openai.com"
    scrubbed = broker.scrub_text(log_sample)
    assert raw_key not in scrubbed
    assert "[REDACTED_SECRET_OPENAI_PROD]" in scrubbed
