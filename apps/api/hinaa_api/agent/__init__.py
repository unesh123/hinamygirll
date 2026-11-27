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
from .contracts import AgentRun, AgentPlan, IntentResult, MOTION_CONTRACT, TurnContext, TurnContextItem, AgentEvent, OperationType, RunStatus, StepState, VerificationResult
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
    ModelContextBudget,
    ProfileBudgets,
    QueryRoute,
    RouteDecision,
    compute_input_budget,
    effective_budgets,
    resolve_model_context_budget,
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
    REPAIRS,
    clamp_min,
    rescale_duration,
    clamp_layer_timing,
)
from .checkpoint import revert, snapshot
from .compaction import compact, estimate_tokens, summarize
from .editor import EditError, str_replace
from .fingerprint import errors_from_exception, fingerprint, normalize_error
from .hooks import GUARDS, apply_guards, duration_cap, guard, layer_timing_guard, scale_floor
from .loop import AgentLoop, ExhaustedError, StuckError
from .verify import verify_image, verify_pdf, verify_video

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
    "AgentRun", "AgentPlan", "IntentResult", "MOTION_CONTRACT", "TurnContext", "TurnContextItem", "AgentEvent", "OperationType", "RunStatus", "StepState", "VerificationResult",
    "ContextBuilder", "ContextCompiler", "CompiledContextBlock", "CompiledPromptContext", "CompiledContextPackage", "ContextIntegrityVerifier", "IntentInterpreter", "PlanValidator", "PlanValidationError", "StepScheduler", "AgentRuntime",
    # Phase B2 — hierarchical context
    "CompactionReason", "ContextCompaction", "ContextItem", "ContextManifest", "ManifestStatus", "PriorityTier", "TrustLevel",
    "ContextProfile", "MemoryQueryRouter", "ModelContextBudget", "ProfileBudgets", "QueryRoute", "RouteDecision", "compute_input_budget", "effective_budgets", "resolve_model_context_budget",
    "DurableTaskBridge", "StepVerificationCondition", "VerificationType",
    # Phase 13
    "VerifierRegistry", "FailureClassifier", "FailureCategory", "VerificationOutcome", "VerificationStatus", "ClassifiedFailure", "get_registry", "get_classifier",
    "RepairController", "LoopDetector", "RepairAction", "RepairDecision",
    # Claude-Code Parity Primitives
    "REPAIRS", "clamp_min", "rescale_duration", "clamp_layer_timing",
    "AgentLoop", "StuckError", "ExhaustedError",
    "EditError", "str_replace",
    "errors_from_exception", "fingerprint", "normalize_error",
    "GUARDS", "apply_guards", "duration_cap", "guard", "layer_timing_guard", "scale_floor",
    "verify_image", "verify_pdf", "verify_video",
    "compact", "estimate_tokens", "summarize",
    "snapshot", "revert",
]
