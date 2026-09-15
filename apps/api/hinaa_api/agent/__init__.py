from __future__ import annotations

from .state import (
    AgentGoal,
    GoalType,
    PlanStep,
    StepStatus,
    StepResult,
    VerificationReport,
    AgentResult,
)
from .planner import AgentPlanner
from .verifier import AgentVerifier
from .kernel import HinaaAgent
from .contracts import AgentRun, AgentPlan, IntentResult, TurnContext, TurnContextItem, AgentEvent, OperationType, RunStatus, StepState, VerificationResult
from .context import ContextBuilder
from .compiler import (
    CompiledContextBlock,
    CompiledContextPackage,
    CompiledPromptContext,
    ContextCompiler,
    ContextIntegrityVerifier,
)
from .context_items import (
    CompactionReason,
    ContextCompaction,
    ContextItem,
    ContextManifest,
    ManifestStatus,
    PriorityTier,
    TrustLevel,
)
from .context_profiles import (
    ContextProfile,
    MemoryQueryRouter,
    ProfileBudgets,
    QueryRoute,
    RouteDecision,
    compute_input_budget,
    effective_budgets,
)
from .intent import IntentInterpreter
from .validation import PlanValidator, PlanValidationError
from .scheduler import StepScheduler
from .runtime import AgentRuntime
from .bridge import DurableTaskBridge, StepVerificationCondition, VerificationType
# Phase 13 — Verification Engine + Self-Repair
from .verifier_registry import (
    VerifierRegistry,
    FailureClassifier,
    FailureCategory,
    VerificationOutcome,
    VerificationStatus,
    ClassifiedFailure,
    get_registry,
    get_classifier,
)
from .repair import (
    RepairController,
    LoopDetector,
    RepairAction,
    RepairDecision,
)

__all__ = [
    "AgentGoal",
    "GoalType",
    "PlanStep",
    "StepStatus",
    "StepResult",
    "VerificationReport",
    "AgentResult",
    "AgentPlanner",
    "AgentVerifier",
    "HinaaAgent",
    "AgentRun", "AgentPlan", "IntentResult", "TurnContext", "TurnContextItem", "AgentEvent", "OperationType", "RunStatus", "StepState", "VerificationResult",
    "ContextBuilder", "ContextCompiler", "CompiledContextBlock", "CompiledPromptContext", "CompiledContextPackage", "ContextIntegrityVerifier", "IntentInterpreter", "PlanValidator", "PlanValidationError", "StepScheduler", "AgentRuntime",
    # Phase B2 — hierarchical context
    "CompactionReason", "ContextCompaction", "ContextItem", "ContextManifest", "ManifestStatus", "PriorityTier", "TrustLevel",
    "ContextProfile", "MemoryQueryRouter", "ProfileBudgets", "QueryRoute", "RouteDecision", "compute_input_budget", "effective_budgets",
    "DurableTaskBridge", "StepVerificationCondition", "VerificationType",
    # Phase 13
    "VerifierRegistry", "FailureClassifier", "FailureCategory", "VerificationOutcome", "VerificationStatus", "ClassifiedFailure", "get_registry", "get_classifier",
    "RepairController", "LoopDetector", "RepairAction", "RepairDecision",
]
