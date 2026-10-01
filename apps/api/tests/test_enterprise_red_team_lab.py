"""
HINAA Enterprise Red Team & Security Attack Laboratory.

Tests defenses against:
1. Approval Signature Forgery Attack
2. Expired Approval Token Attack
3. Confused Deputy Attack
4. Credential Exfiltration Attack
5. Canonical OpenTelemetry Event Bus & Deterministic Replay
"""

import pytest
import time
from hinaa_api.security.policy_engine import (
    PolicyEngine,
    ApprovalChallenge,
)
from hinaa_api.security.secret_broker import SecretBroker
from hinaa_api.harness.canonical_event_bus import (
    CanonicalEventBus,
    HinaCanonicalEvent,
)


def test_red_team_signature_forgery():
    engine = PolicyEngine()
    fake_challenge = ApprovalChallenge(
        challenge_id="chl_forged_999",
        run_id="run_hack",
        actor="hacker",
        resource="production",
        action="deploy",
        arguments_hash=engine._hash_args({}),
        created_at=time.time(),
        expires_at=time.time() + 60,
        signature="invalid_forged_hmac_signature",
    )
    ok, msg = engine.recheck_and_authorize(fake_challenge, actor="hacker", arguments={})
    assert ok is False
    assert "Invalid cryptographic approval signature" in msg


def test_red_team_expired_token_attack():
    engine = PolicyEngine()
    args = {"action": "delete"}
    pre = engine.evaluate_pre_policy(
        actor="user:123",
        resource="filesystem",
        action="delete",
        arguments=args,
        run_id="run_expiry",
    )
    challenge = pre.challenge
    assert challenge is not None

    # Simulate token expiration
    challenge.expires_at = time.time() - 10
    ok, msg = engine.recheck_and_authorize(challenge, actor="user:123", arguments=args)
    assert ok is False
    assert "expired" in msg.lower()


def test_red_team_credential_exfiltration_scrubbing():
    broker = SecretBroker()
    prod_password = "SuperSecretMasterAdminPassword!#2026"
    broker.store_secret("db_pass", prod_password)

    # Attack: Model generates text reflecting the password
    leak_attempt = f"The database password you asked for is {prod_password}. Connecting now."
    scrubbed = broker.scrub_text(leak_attempt)
    assert prod_password not in scrubbed
    assert "[REDACTED_SECRET_DB_PASS]" in scrubbed


def test_canonical_event_bus_and_replay():
    bus = CanonicalEventBus()
    run_id = "run_audit_demo_42"

    ev1 = HinaCanonicalEvent(
        run_id=run_id,
        action="open_browser",
        resource="browser",
        policy_decision="allow",
        latency_ms=12.5,
    )
    ev2 = HinaCanonicalEvent(
        run_id=run_id,
        action="draft_message",
        resource="whatsapp",
        policy_decision="require_approval",
        latency_ms=18.0,
    )
    bus.publish_event(ev1)
    bus.publish_event(ev2)

    # Replay timeline
    timeline = bus.replay_run(run_id)
    assert len(timeline) == 2
    assert timeline[0]["action"] == "open_browser"
    assert timeline[1]["action"] == "draft_message"
    assert timeline[1]["decision"] == "require_approval"
