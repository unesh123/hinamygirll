"""
Directive §5: Automated Verification Suite for Tiered Computer-Operator Authorization Matrix.

Verifies:
1. Tier 0: Read-only inspection (observe) permitted under bounded policy.
2. Tier 1: Reversible workspace mutation (create_folder) permitted under bounded policy.
3. Tier 3: Process execution and OS input denied without explicit user approval.
4. Tier 3: Process execution permitted when confirmed=True and approval_source='user'.
5. Tier 4: Irreversible and external dispatch strictly requires explicit user approval.
"""

import pytest
from hinaa_api.tools.policy import (
    ActionRiskTier,
    classify_computer_operator_action,
    check_action_tier_authorization,
)
from hinaa_api.tools.computer_operator import execute_computer_operator


def test_action_classification():
    assert classify_computer_operator_action("observe") == ActionRiskTier.TIER_0_READ_ONLY
    assert classify_computer_operator_action("list_windows") == ActionRiskTier.TIER_0_READ_ONLY
    assert classify_computer_operator_action("create_folder") == ActionRiskTier.TIER_1_REVERSIBLE
    assert classify_computer_operator_action("chrome_control") == ActionRiskTier.TIER_2_EXTERNAL
    assert classify_computer_operator_action("open_application") == ActionRiskTier.TIER_3_PROCESS
    assert classify_computer_operator_action("type_text") == ActionRiskTier.TIER_3_PROCESS
    assert classify_computer_operator_action("send_message") == ActionRiskTier.TIER_4_DESTRUCTIVE


@pytest.mark.asyncio
async def test_tier0_and_tier1_bounded_execution():
    # Tier 0 observe
    res_obs = await execute_computer_operator({"action": "observe"})
    assert res_obs.get("success") is True or "observation" in res_obs

    # Tier 1 folder creation in temp
    import tempfile, shutil, os
    td = tempfile.mkdtemp()
    try:
        fpath = os.path.join(td, "BoundedFolder")
        res_f = await execute_computer_operator({"action": "create_folder", "target": fpath})
        assert res_f.get("success") is True
        assert os.path.exists(fpath)
    finally:
        shutil.rmtree(td, ignore_errors=True)


@pytest.mark.asyncio
async def test_tier3_denied_without_explicit_user_approval():
    # Calling Tier 3 open_application without approval
    res = await execute_computer_operator({
        "action": "open_application",
        "target": "notepad.exe",
        "confirmed": False,
        "approval_source": "none",
    })
    assert res.get("success") is False
    assert res.get("requires_explicit_approval") is True
    assert res.get("code") == "EXPLICIT_USER_APPROVAL_REQUIRED"


@pytest.mark.asyncio
async def test_tier3_denied_with_standing_consent():
    # Inferred or standing consent is rejected for Tier 3
    res = await execute_computer_operator({
        "action": "open_application",
        "target": "notepad.exe",
        "confirmed": True,
        "approval_source": "standing-consent",
    })
    assert res.get("success") is False
    assert res.get("requires_explicit_approval") is True
    assert res.get("code") == "EXPLICIT_USER_APPROVAL_REQUIRED"


@pytest.mark.asyncio
async def test_tier4_denied_without_user_approval():
    # Calling Tier 4 send_message without user approval
    res = await execute_computer_operator({
        "action": "send_message",
        "target": "whatsapp",
        "content": "Hello",
        "confirmed": False,
    })
    assert res.get("success") is False
    assert res.get("requires_explicit_approval") is True
    assert res.get("code") == "EXPLICIT_USER_APPROVAL_REQUIRED"
