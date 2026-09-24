"""HINAA Global Cost Policy Engine

Enforces the global 20-credit threshold:
- Total job cost < 20 credits: auto-executes with the selected or cheapest suitable model.
- Total job cost >= 20 credits: requires explicit confirmation, recommending the chosen model
  alongside an economy alternative (e.g. Classic Fast at 1 cr/img or Flux.1 Fast at 5 cr/img).
- Insufficient credits: blocks execution with an explicit balance explanation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .registry import CANONICAL_MODELS, CreativeModelRegistry


GLOBAL_CREDIT_AUTO_THRESHOLD = 20


class PolicyDecision(str, Enum):
    ALLOW_AUTO = "allow_auto"
    WAITING_APPROVAL = "waiting_approval"
    DENY_BUDGET = "deny_budget"


@dataclass(frozen=True, slots=True)
class CostPolicyEvaluation:
    decision: PolicyDecision
    total_cost_credits: int
    unit_cost_credits: int
    quantity: int
    requested_model: str
    remaining_balance: int
    requires_user_confirmation: bool
    recommended_model: str
    economy_alternative_model: str | None
    economy_alternative_cost: int | None
    savings_credits: int | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "totalCostCredits": self.total_cost_credits,
            "unitCostCredits": self.unit_cost_credits,
            "quantity": self.quantity,
            "requestedModel": self.requested_model,
            "remainingBalance": self.remaining_balance,
            "requiresUserConfirmation": self.requires_user_confirmation,
            "recommendedModel": self.recommended_model,
            "economyAlternativeModel": self.economy_alternative_model,
            "economyAlternativeCost": self.economy_alternative_cost,
            "savingsCredits": self.savings_credits,
            "reason": self.reason,
        }


class CostPolicyEngine:
    @staticmethod
    def calculate_cost(
        model_id: str,
        quantity: int = 1,
        *,
        width: int = 1024,
        height: int = 1024,
        scale: float = 1.0,
    ) -> int:
        qty = max(1, quantity)
        if model_id.startswith("upscale-"):
            unit = CreativeModelRegistry.calculate_upscale_credits(width, height, scale)
            return unit * qty

        model = CANONICAL_MODELS.get(model_id)
        unit = model.cost_credits if model else 5
        return unit * qty

    @classmethod
    def evaluate(
        cls,
        model_id: str,
        quantity: int = 1,
        *,
        current_balance: int = 45000,
        confirmed: bool = False,
        width: int = 1024,
        height: int = 1024,
        scale: float = 1.0,
    ) -> CostPolicyEvaluation:
        qty = max(1, quantity)
        total_cost = cls.calculate_cost(model_id, qty, width=width, height=height, scale=scale)
        unit_cost = max(1, total_cost // qty)

        if total_cost > current_balance and not confirmed:
            return CostPolicyEvaluation(
                decision=PolicyDecision.DENY_BUDGET,
                total_cost_credits=total_cost,
                unit_cost_credits=unit_cost,
                quantity=qty,
                requested_model=model_id,
                remaining_balance=current_balance,
                requires_user_confirmation=True,
                recommended_model=model_id,
                economy_alternative_model="classic-fast",
                economy_alternative_cost=1 * qty,
                savings_credits=max(0, total_cost - (1 * qty)),
                reason=(
                    f"Insufficient credits. Job requires {total_cost} credits, "
                    f"but only {current_balance} credits remain in your balance."
                ),
            )

        economy_model = "classic-fast" if model_id != "classic-fast" else "flux-fast"
        economy_cost = cls.calculate_cost(economy_model, qty)
        savings = max(0, total_cost - economy_cost)

        if total_cost >= GLOBAL_CREDIT_AUTO_THRESHOLD and not confirmed:
            return CostPolicyEvaluation(
                decision=PolicyDecision.WAITING_APPROVAL,
                total_cost_credits=total_cost,
                unit_cost_credits=unit_cost,
                quantity=qty,
                requested_model=model_id,
                remaining_balance=current_balance,
                requires_user_confirmation=True,
                recommended_model=model_id,
                economy_alternative_model=economy_model,
                economy_alternative_cost=economy_cost,
                savings_credits=savings,
                reason=(
                    f"High-credit action ({total_cost} credits >= 20 credit threshold). "
                    f"Explicit user confirmation required before spending credits."
                ),
            )

        return CostPolicyEvaluation(
            decision=PolicyDecision.ALLOW_AUTO,
            total_cost_credits=total_cost,
            unit_cost_credits=unit_cost,
            quantity=qty,
            requested_model=model_id,
            remaining_balance=current_balance,
            requires_user_confirmation=False,
            recommended_model=model_id,
            economy_alternative_model=economy_model if total_cost >= GLOBAL_CREDIT_AUTO_THRESHOLD else None,
            economy_alternative_cost=economy_cost if total_cost >= GLOBAL_CREDIT_AUTO_THRESHOLD else None,
            savings_credits=savings if total_cost >= GLOBAL_CREDIT_AUTO_THRESHOLD else None,
            reason="Approved under global cost policy.",
        )
