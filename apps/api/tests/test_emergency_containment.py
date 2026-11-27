import os
import pytest
from hinaa_api.tools import QUARANTINED_DANGEROUS_TOOLS, load_all_tools, registry
from hinaa_api.tools.full_pc_control import FullPCControl
from hinaa_api.tools.multi_account import MultiAccountManager
from hinaa_api.tools.uncensored_mode import UncensoredMode
from hinaa_api.tools import policy as tool_policy
from hinaa_api.config import Settings


def test_quarantined_tools_not_in_registry():
    """Verify quarantined dangerous tools are never registered."""
    load_all_tools()
    registered = registry.list_tools()
    for tool_name in QUARANTINED_DANGEROUS_TOOLS:
        assert tool_name not in registered, f"Quarantined tool '{tool_name}' must not be registered"


def test_uncensored_mode_permanently_disabled():
    """Verify uncensored mode cannot be enabled and safety bypass always returns False."""
    UncensoredMode.enable()
    assert not UncensoredMode.is_on()
    assert not UncensoredMode.should_bypass_gate("terminal_execute", {})
    assert not UncensoredMode.should_allow_dangerous()

    UncensoredMode.disable()
    assert not UncensoredMode.is_on()


@pytest.mark.asyncio
async def test_full_pc_control_fail_closed():
    """Verify FullPCControl fails closed on all actions."""
    pc = FullPCControl()
    res = await pc.run_command("whoami")
    assert not res["ok"]
    assert "TOOL_CONTAINED" in res["error"]

    read_res = pc.read_file("some_secret.txt")
    assert "CONTAINED" in read_res

    write_res = pc.write_file("test.txt", "payload")
    assert "CONTAINED" in write_res

    exec_res = await pc.execute({"action": "run_command", "cmd": "dir"})
    assert not exec_res["ok"]
    assert "TOOL_CONTAINED" in exec_res["error"]


def test_multi_account_fail_closed():
    """Verify MultiAccountManager refuses credential manipulation and plaintext storage."""
    mgr = MultiAccountManager()
    add_res = mgr.add_account("test", "google", "test@example.com", "pass123")
    assert not add_res.get("ok", True)
    assert "TOOL_CONTAINED" in add_res.get("error", "")

    exec_res = mgr.execute({"action": "add", "name": "bad"})
    assert not exec_res.get("ok", True)


def test_confirmation_waived_ignores_env_vars(monkeypatch):
    """Verify confirmation_waived is not bypassed by HINAA_FULL_AUTONOMY or HINAA_AUTO_APPROVE."""
    monkeypatch.setenv("HINAA_FULL_AUTONOMY", "true")
    monkeypatch.setenv("HINAA_AUTO_APPROVE", "1")

    assert not tool_policy.confirmation_waived("terminal_execute")
    assert not tool_policy.confirmation_waived("file_write")
    assert not tool_policy.confirmation_waived("browser_click")


def test_remote_host_cannot_execute_local_or_irreversible_tools():
    """Verify remote host cannot execute local effect or irreversible external tools."""
    settings = Settings(allow_remote_local_tools=False)
    remote_host = "public-api.hina.ai"

    # Local effect tool from remote
    verdict_local = tool_policy.decide("terminal_execute", settings, remote_host)
    assert not verdict_local.permitted
    assert verdict_local.code == "LOCAL_TOOL_NOT_PERMITTED"

    # Irreversible external tool from remote
    verdict_ext = tool_policy.decide("send_email", settings, remote_host)
    assert not verdict_ext.permitted
    assert verdict_ext.code == "IRREVERSIBLE_TOOL_NOT_PERMITTED"

    # Loopback host is permitted for local effect tools
    verdict_loopback = tool_policy.decide("terminal_execute", settings, "127.0.0.1:8000")
    assert verdict_loopback.permitted


def test_action_tier_authorization():
    """Verify Tier 2, Tier 3, and Tier 4 require explicit user approval."""
    # Tier 0 & 1 don't require explicit user confirmation
    v0 = tool_policy.check_action_tier_authorization(tool_policy.ActionRiskTier.TIER_0_READ_ONLY)
    assert v0.permitted

    v1 = tool_policy.check_action_tier_authorization(tool_policy.ActionRiskTier.TIER_1_REVERSIBLE)
    assert v1.permitted

    # Tier 2, 3, 4 without confirmation
    for tier in (
        tool_policy.ActionRiskTier.TIER_2_EXTERNAL,
        tool_policy.ActionRiskTier.TIER_3_PROCESS,
        tool_policy.ActionRiskTier.TIER_4_DESTRUCTIVE,
    ):
        v = tool_policy.check_action_tier_authorization(tier, confirmed=False, approval_source="none")
        assert not v.permitted
        assert v.code == "EXPLICIT_USER_APPROVAL_REQUIRED"

        # Even if confirmed=True, approval_source must be 'user'
        v_agent = tool_policy.check_action_tier_authorization(tier, confirmed=True, approval_source="agent")
        assert not v_agent.permitted

        # Passing confirmed=True and approval_source='user' succeeds
        v_ok = tool_policy.check_action_tier_authorization(tier, confirmed=True, approval_source="user")
        assert v_ok.permitted
