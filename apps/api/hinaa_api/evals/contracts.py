"""
HINAA OS — Phase 16 Self-Improvement & Continuous Eval Harness
Data Contracts, Enums, and Pydantic Schemas.

Covers:
- Immutable dataset versioning and partition isolation (Dev, Val, Sealed Holdout)
- Reproducible run manifests with git commit, hardware, and model fingerprints
- Multi-dimensional scoring rubrics (correctness, groundedness, completeness, safety, latency, cost)
- Structured improvement proposals with blast radius bounds and authorization tiers
- Canary deployment, staged traffic assignment, and automated rollback receipts
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class EvalRunStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SCORING = "SCORING"
    VERIFIED = "VERIFIED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class CandidateStatus(str, Enum):
    PROPOSED = "PROPOSED"
    SANDBOXED = "SANDBOXED"
    EVAL_READY = "EVAL_READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    CANARY = "CANARY"
    PROMOTED = "PROMOTED"
    ROLLED_BACK = "ROLLED_BACK"
    REJECTED = "REJECTED"


class EvalCaseDomain(str, Enum):
    REASONING = "REASONING"
    RESEARCH = "RESEARCH"
    CODING = "CODING"
    BILINGUAL = "BILINGUAL"
    REFLECTIVE_VOICE = "REFLECTIVE_VOICE"
    MEMORY = "MEMORY"
    TOOLS_AGENTS = "TOOLS_AGENTS"
    MULTIMODAL_COMMERCE = "MULTIMODAL_COMMERCE"


class EvalClass(str, Enum):
    UNIT = "UNIT"
    INTEGRATION = "INTEGRATION"
    LIVE_API = "LIVE_API"
    LIVE_BROWSER = "LIVE_BROWSER"
    HUMAN = "HUMAN"
    OS_SECURITY = "OS_SECURITY"
    REGRESSION = "REGRESSION"


class DatasetPartition(str, Enum):
    DEV_POOL = "DEV_POOL"          # 60% - Accessible for iterative candidate diagnosis
    VAL_POOL = "VAL_POOL"          # 20% - Accessible for internal candidate tuning
    SEALED_HOLDOUT = "SEALED_HOLDOUT"  # 20% - Sealed from candidate agents; final promotion gate only


class ScorerType(str, Enum):
    DETERMINISTIC_ARTIFACT = "DETERMINISTIC_ARTIFACT"
    DETERMINISTIC_HASH = "DETERMINISTIC_HASH"
    DETERMINISTIC_EXIT_CODE = "DETERMINISTIC_EXIT_CODE"
    CITATION_GROUNDEDNESS = "CITATION_GROUNDEDNESS"
    BLINDED_PAIRWISE_JUDGE = "BLINDED_PAIRWISE_JUDGE"
    REFLECTIVE_SPEECH_METRICS = "REFLECTIVE_SPEECH_METRICS"
    SECURITY_GATE_ORACLE = "SECURITY_GATE_ORACLE"
    HUMAN_CALIBRATED = "HUMAN_CALIBRATED"


class PromotionOutcome(str, Enum):
    PROMOTED = "PROMOTED"
    REJECTED_GATE_FAILURE = "REJECTED_GATE_FAILURE"
    REJECTED_SECURITY_VETO = "REJECTED_SECURITY_VETO"
    ROLLED_BACK_CANARY = "ROLLED_BACK_CANARY"


class FailureCluster(str, Enum):
    REASONING_ERROR = "REASONING_ERROR"
    WRONG_TOOL = "WRONG_TOOL"
    CITATION_MISMATCH = "CITATION_MISMATCH"
    EXCESSIVE_VERBOSITY = "EXCESSIVE_VERBOSITY"
    STALE_MEMORY = "STALE_MEMORY"
    NEPALI_MISTRANSLATION = "NEPALI_MISTRANSLATION"
    TIMEOUT = "TIMEOUT"
    AUDIO_DUPLICATION = "AUDIO_DUPLICATION"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    PERMISSION_FAILURE = "PERMISSION_FAILURE"


class EvalCase(BaseModel):
    case_id: str
    domain: EvalCaseDomain
    partition: DatasetPartition
    eval_class: EvalClass
    prompt: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    expected_outputs: Dict[str, Any] = Field(default_factory=dict)
    scorer_type: ScorerType
    scorer_config: Dict[str, Any] = Field(default_factory=dict)
    provenance: str = "curated_consented_benchmark"
    tags: List[str] = Field(default_factory=list)
    is_adversarial: bool = False
    created_at: float = Field(default_factory=time.time)


class DatasetManifest(BaseModel):
    dataset_id: str
    version: str = "1.0.0"
    dataset_hash: str  # SHA-256 of all canonical case contents
    total_cases: int
    dev_count: int
    val_count: int
    holdout_count: int
    domain_counts: Dict[str, int] = Field(default_factory=dict)
    frozen_at: float = Field(default_factory=time.time)
    license_metadata: str = "Internal Consented Non-PII Benchmark"


class CandidateChange(BaseModel):
    candidate_id: str
    proposal_id: str
    target_layer: str  # "prompts", "retrieval", "examples", "routing", "speech_template"
    description: str
    patch_diff: str
    config_hash_before: str
    config_hash_after: str
    weights_updated: bool = False  # Strictly False unless genuine ML training job executed
    status: CandidateStatus = CandidateStatus.PROPOSED
    created_at: float = Field(default_factory=time.time)


class BaselineSnapshot(BaseModel):
    snapshot_id: str
    git_commit: str
    config_hashes: Dict[str, str] = Field(default_factory=dict)
    model_fingerprint: str
    created_at: float = Field(default_factory=time.time)


class TraceReceipt(BaseModel):
    trace_id: str
    case_id: str
    run_id: str
    candidate_id: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_paisa: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    tool_calls_count: int = 0
    redacted_trace: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class QualityMetrics(BaseModel):
    correctness: float = 1.0     # 0.0 to 1.0
    groundedness: float = 1.0    # 0.0 to 1.0
    completeness: float = 1.0    # 0.0 to 1.0
    instruction_adherence: float = 1.0
    safety_compliance: float = 1.0
    language_naturalness: float = 1.0
    latency_score: float = 1.0
    cost_efficiency: float = 1.0


class ScoreResult(BaseModel):
    score_id: str
    case_id: str
    run_id: str
    candidate_id: Optional[str] = None
    evaluator_name: str
    score: float  # Normalized 0.0 to 1.0
    passed: bool
    metrics: QualityMetrics = Field(default_factory=QualityMetrics)
    details: Dict[str, Any] = Field(default_factory=dict)
    confidence_interval: Optional[List[float]] = None
    created_at: float = Field(default_factory=time.time)


class JudgeCalibration(BaseModel):
    calibration_id: str
    judge_model_id: str
    agreement_with_humans: float
    position_bias_rate: float
    verbosity_bias_rate: float
    false_positive_rate: float
    false_negative_rate: float
    calibrated_at: float = Field(default_factory=time.time)


class ImprovementProposal(BaseModel):
    proposal_id: str
    symptom: str
    failure_cluster: FailureCluster
    evidence_trace_ids: List[str]
    patch_scope: str  # "prompts", "retrieval", "routing", etc.
    expected_metric: str
    target_threshold: float
    blast_radius: str = "LOW"  # LOW, MEDIUM, HIGH
    authorization_tier: str = "OPERATOR"
    baseline_snapshot_id: str
    created_at: float = Field(default_factory=time.time)


class CanaryAssignment(BaseModel):
    canary_id: str
    candidate_id: str
    scope_percentage: int = 10
    assigned_tasks_count: int = 0
    status: str = "ACTIVE"  # ACTIVE, PAUSED, ROLLED_BACK, COMPLETED
    health_check_interval_seconds: int = 30
    started_at: float = Field(default_factory=time.time)


class RollbackReceipt(BaseModel):
    rollback_id: str
    candidate_id: str
    trigger_reason: str
    restored_config_hash: str
    restored_at: float = Field(default_factory=time.time)
    restored_by: str = "system_canary_guard"


class PromotionDecision(BaseModel):
    decision_id: str
    candidate_id: str
    primary_metric_gain: float
    is_statistically_significant: bool
    holdout_hash: str
    security_gate_passed: bool
    human_approver_id: str
    approval_token_id: str
    outcome: PromotionOutcome
    decided_at: float = Field(default_factory=time.time)


class EvalRunManifest(BaseModel):
    run_id: str
    eval_suite_id: str
    dataset_id: str
    dataset_hash: str
    baseline_snapshot_id: str
    candidate_id: Optional[str] = None
    status: EvalRunStatus = EvalRunStatus.CREATED
    cases_total: int = 0
    cases_completed: int = 0
    cases_passed: int = 0
    cases_failed: int = 0
    cases_blocked: int = 0
    total_tokens: int = 0
    total_cost_paisa: int = 0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    git_commit: str = ""
    hardware_fingerprint: str = ""
    started_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
