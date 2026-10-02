"""
Tests for HINAA Enterprise Policy Engine, Data Lake, and Resilient Router.
"""

import shutil
import tempfile
import time
import pytest
from pathlib import Path

from hinaa_api.cognitive.contracts import Goal, WorldState, UserState, CognitiveRun, HinaEvent
from hinaa_api.cognitive.policy_engine import EnterprisePolicyEngine, RiskTier, PolicyDecision
from hinaa_api.cognitive.data_lake import DataLakeIngestor
from hinaa_api.cognitive.resilient_router import ResilientProviderRouter, CircuitState
from hinaa_api.cognitive.kernel import CognitiveKernel


def test_enterprise_policy_tiers():
    engine = EnterprisePolicyEngine()

    # Tier 0 Readonly
    d0 = engine.evaluate(action="search_web")
    assert d0.allowed is True
    assert d0.risk_tier == RiskTier.TIER_0_READONLY
    assert d0.requires_approval is False

    # Tier 2 System Actuation
    d2 = engine.evaluate(action="app_launch", parameters={"app_name": "notepad"})
    assert d2.allowed is True
    assert d2.risk_tier == RiskTier.TIER_2_SYSTEM_ACTUATION

    # Tier 2 System Actuation with dangerous command blocked
    d2_danger = engine.evaluate(action="app_launch", parameters={"app_name": "powershell -enc aW1wb3J0"})
    assert d2_danger.allowed is False
    assert d2_danger.requires_approval is True

    # Tier 3 Critical requires approval token
    d3 = engine.evaluate(action="delete_file", resource="/important.txt")
    assert d3.allowed is False
    assert d3.risk_tier == RiskTier.TIER_3_CRITICAL
    assert d3.requires_approval is True
    assert d3.approval_token is not None

    # Test token verification
    token = d3.approval_token
    d3_approved = engine.evaluate(action="delete_file", resource="/important.txt", approval_token=token)
    assert d3_approved.allowed is True
    assert d3_approved.requires_approval is False


def test_secret_redaction():
    text_with_keys = "My OpenAI key is sk-abcdef1234567890123456789012 and token is Bearer secret_access_token_12345"
    redacted = EnterprisePolicyEngine.redact_secrets(text_with_keys)
    assert "sk-" not in redacted
    assert "[REDACTED_SECRET]" in redacted

    dict_with_secrets = {
        "password": "supersecretpassword123",
        "api_key": "AIzaSyD-1234567890abcdefghijklmnopq",
        "user": "developer",
    }
    redacted_dict = EnterprisePolicyEngine.redact_secrets(dict_with_secrets)
    assert redacted_dict["password"] == "[REDACTED_CREDENTIAL]"
    assert redacted_dict["api_key"] == "[REDACTED_CREDENTIAL]"
    assert redacted_dict["user"] == "developer"


def test_audit_hash_chain_integrity():
    engine = EnterprisePolicyEngine()
    d1 = engine.evaluate("search_web")
    d2 = engine.evaluate("app_launch", parameters={"app_name": "calc"})
    d3 = engine.evaluate("delete_file", resource="/test.dat")

    engine.record_audit(user_id="u1", action="search_web", resource="web", decision=d1)
    engine.record_audit(user_id="u1", action="app_launch", resource="calc", decision=d2)
    engine.record_audit(user_id="u1", action="delete_file", resource="/test.dat", decision=d3)

    assert engine.verify_audit_integrity() is True
    records = engine.get_recent_audit_records()
    assert len(records) >= 3


def test_data_lake_ingestor():
    temp_dir = tempfile.mkdtemp()
    try:
        lake = DataLakeIngestor(lake_root=Path(temp_dir) / "lake")
        evt = HinaEvent(
            run_id="run_123",
            session_id="sess_123",
            user_id="u_enterprise",
            event_type="test.event",
            payload={"message": "hello enterprise data lake", "api_key": "sk-secret12345678901234567890"},
        )
        lake.record_event(evt)
        count = lake.flush_sync()
        assert count == 1

        events = lake.query_events(user_id="u_enterprise")
        assert len(events) == 1
        assert events[0]["payload"]["message"] == "hello enterprise data lake"
        assert events[0]["payload"]["api_key"] == "[REDACTED_CREDENTIAL]"

        stats = lake.get_statistics()
        assert stats["totalEventsIngested"] == 1

        archive = lake.export_compliance_archive(user_id="u_enterprise")
        assert archive["userId"] == "u_enterprise"
        assert archive["totalEvents"] == 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_resilient_provider_router():
    router = ResilientProviderRouter(failure_threshold=2, recovery_timeout_seconds=0.1)

    # Initially healthy
    assert router.get_provider_status("claude").state == CircuitState.CLOSED
    chain = router.select_healthy_provider_chain("claude")
    assert chain[0] == "claude"

    # 1 failure: still closed
    router.record_failure("claude", Exception("timeout 1"))
    assert router.get_provider_status("claude").state == CircuitState.CLOSED

    # 2 failures: trips breaker -> OPEN
    router.record_failure("claude", Exception("timeout 2"))
    assert router.get_provider_status("claude").state == CircuitState.OPEN

    # Healthy chain no longer has claude at the front
    chain_tripped = router.select_healthy_provider_chain("claude")
    assert "claude" not in chain_tripped

    # Wait for recovery timeout
    time.sleep(0.15)
    # Status should transition to HALF_OPEN upon query
    st = router.get_provider_status("claude")
    assert st.state == CircuitState.HALF_OPEN

    # Success restores it to CLOSED
    router.record_success("claude", latency_ms=120.0)
    assert router.get_provider_status("claude").state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_cognitive_kernel_enterprise_turn():
    temp_dir = tempfile.mkdtemp()
    try:
        policy = EnterprisePolicyEngine()
        lake = DataLakeIngestor(lake_root=Path(temp_dir) / "lake")
        router = ResilientProviderRouter()

        kernel = CognitiveKernel(
            policy_engine=policy,
            data_lake=lake,
            resilient_router=router,
        )

        run = await kernel.execute_turn(
            "Open calc on my machine",
            user_id="enterprise_tester",
            session_id="sess_ent_001",
        )

        assert run.status in ("completed", "executing")
        assert run.goal.goal_type == "computer_use"
        assert len(lake.query_events(user_id="enterprise_tester")) >= 1
        assert policy.verify_audit_integrity() is True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
