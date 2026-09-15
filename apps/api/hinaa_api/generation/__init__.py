"""HINAA generation engine — coherent long-form output.

This package owns the *connective intelligence* of long generation:
continuation state, seam deduplication, structural continuation detection,
and final-output consistency checks. Providers consume it; they do not
re-implement these policies.
"""

from .continuation import (
    ContinuationDecision,
    GenerationContinuationState,
    ContinuationStatus,
    ContinuationNeeded,
    ContinuationReason,
    detect_continuation_need,
    seam_dedup,
    SeamGuard,
    run_consistency_pass,
)
from .orchestrator import (
    GenerationFinishReason,
    GenerationProviderCapabilities,
    GenerationOrchestrator,
    OrchestratorOutcome,
    SegmentResult,
    ProviderSegmentStream,
    map_finish_reason,
    OPENAI_FINISH_REASON_MAP,
    GEMINI_FINISH_REASON_MAP,
)
from .continuation_contract import (
    ContinuationRequest,
    render_continuation_prompt,
    PromptInvariantVerifier,
)

__all__ = [
    "ContinuationDecision",
    "GenerationContinuationState",
    "ContinuationStatus",
    "ContinuationNeeded",
    "ContinuationReason",
    "detect_continuation_need",
    "seam_dedup",
    "SeamGuard",
    "run_consistency_pass",
    "GenerationFinishReason",
    "GenerationProviderCapabilities",
    "GenerationOrchestrator",
    "OrchestratorOutcome",
    "SegmentResult",
    "ProviderSegmentStream",
    "map_finish_reason",
    "OPENAI_FINISH_REASON_MAP",
    "GEMINI_FINISH_REASON_MAP",
    "ContinuationRequest",
    "render_continuation_prompt",
    "PromptInvariantVerifier",
]
