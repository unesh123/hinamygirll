import pytest
from hinaa_api.creative import (
    CostPolicyEngine,
    PolicyDecision,
)

def test_under_20_credits_allows_auto():
    # 1 credit: classic-fast
    eval_1 = CostPolicyEngine.evaluate("classic-fast", quantity=1, current_balance=1000)
    assert eval_1.decision == PolicyDecision.ALLOW_AUTO
    assert eval_1.total_cost_credits == 1
    assert not eval_1.requires_user_confirmation

    # 10 credits: flux-1 (1 image)
    eval_10 = CostPolicyEngine.evaluate("flux-1", quantity=1, current_balance=1000)
    assert eval_10.decision == PolicyDecision.ALLOW_AUTO
    assert eval_10.total_cost_credits == 10
    assert not eval_10.requires_user_confirmation

def test_20_or_more_credits_requires_confirmation():
    # 20 credits: flux-1 (2 images)
    eval_20 = CostPolicyEngine.evaluate("flux-1", quantity=2, current_balance=1000, confirmed=False)
    assert eval_20.decision == PolicyDecision.WAITING_APPROVAL
    assert eval_20.total_cost_credits == 20
    assert eval_20.requires_user_confirmation
    assert eval_20.economy_alternative_model == "classic-fast"
    assert eval_20.economy_alternative_cost == 2
    assert eval_20.savings_credits == 18

    # 45 credits: mystic-1 (1 image)
    eval_45 = CostPolicyEngine.evaluate("mystic-1", quantity=1, current_balance=1000, confirmed=False)
    assert eval_45.decision == PolicyDecision.WAITING_APPROVAL
    assert eval_45.total_cost_credits == 45
    assert eval_45.requires_user_confirmation
    assert eval_45.economy_alternative_cost == 1
    assert eval_45.savings_credits == 44

def test_confirmed_allows_auto_for_high_credit_job():
    eval_confirmed = CostPolicyEngine.evaluate("mystic-1", quantity=1, current_balance=1000, confirmed=True)
    assert eval_confirmed.decision == PolicyDecision.ALLOW_AUTO
    assert eval_confirmed.total_cost_credits == 45
    assert not eval_confirmed.requires_user_confirmation

def test_insufficient_budget_denies():
    eval_deny = CostPolicyEngine.evaluate("mystic-1", quantity=1, current_balance=10, confirmed=False)
    assert eval_deny.decision == PolicyDecision.DENY_BUDGET
    assert "Insufficient credits" in eval_deny.reason
