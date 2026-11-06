"""HINAA OS — Phase 16 Evaluation & Continuous Improvement API Endpoints.

Mounts `/api/evals` routes for datasets, evaluation suites, diagnostic proposals,
matched experiments, canary staging, and atomic rollbacks.
Strictly isolates SEALED_HOLDOUT cases from untrusted callers.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from hinaa_api.evals.contracts import (
    CandidateChange,
    CandidateStatus,
    DatasetManifest,
    DatasetPartition,
    EvalCase,
    EvalCaseDomain,
    EvalRunManifest,
    FailureCluster,
    ImprovementProposal,
    PromotionDecision,
    RollbackReceipt,
    ScoreResult,
)
from hinaa_api.evals.dataset import ContaminationCheckResult, DatasetManager
from hinaa_api.evals.promotion import PromotionController
from hinaa_api.evals.proposal import DiagnosticProposalEngine
from hinaa_api.evals.runner import ExperimentRunner, MatchedComparisonResult
from hinaa_api.evals.store import EvalStore

router = APIRouter(prefix="/api/evals", tags=["Evaluation & Continuous Improvement"])

# Global singletons
_store = EvalStore()
_dataset_mgr = DatasetManager()
# Ensure store has canonical dataset
try:
    _store.save_dataset(_dataset_mgr.manifest, _dataset_mgr.list_cases(caller_role="eval_runner"))
except Exception:
    pass

_runner = ExperimentRunner(_store, _dataset_mgr)
_proposal_engine = DiagnosticProposalEngine()
_promotion_ctrl = PromotionController(_store)


# Request & Response Models
class TriggerRunRequest(BaseModel):
    eval_suite_id: str = "suite-on-demand"
    partition: DatasetPartition = DatasetPartition.DEV_POOL
    candidate_id: Optional[str] = None
    baseline_snapshot_id: str = "baseline-snap-p15"


class DiagnoseRequest(BaseModel):
    run_id: str


class MatchedExperimentRequest(BaseModel):
    candidate_id: str
    partition: DatasetPartition = DatasetPartition.VAL_POOL
    baseline_snapshot_id: str = "baseline-snap-p15"


class PromotionRequest(BaseModel):
    security_clean: bool = True
    approval_token: Optional[str] = None
    approver_id: str = "human_operator"


class CanaryRequest(BaseModel):
    traffic_pct: int = 10
    simulated_error_rate: float = 0.0


class RollbackRequest(BaseModel):
    reason: str
    restored_by: str = "human_operator"


class LeakageCheckRequest(BaseModel):
    text: str
    threshold_jaccard: float = 0.65


# 1. Dataset Endpoints
@router.get("/datasets", response_model=List[DatasetManifest])
def list_datasets() -> List[DatasetManifest]:
    """Lists available evaluation dataset manifests."""
    manifest = _store.get_dataset(_dataset_mgr.manifest.dataset_id)
    if not manifest:
        return [_dataset_mgr.manifest]
    return [manifest]


@router.get("/datasets/{dataset_id}", response_model=DatasetManifest)
def get_dataset(dataset_id: str) -> DatasetManifest:
    """Gets specific dataset manifest by ID."""
    manifest = _store.get_dataset(dataset_id)
    if not manifest:
        if dataset_id == _dataset_mgr.manifest.dataset_id:
            return _dataset_mgr.manifest
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found.")
    return manifest


@router.get("/datasets/{dataset_id}/cases", response_model=List[EvalCase])
def list_dataset_cases(
    dataset_id: str,
    domain: Optional[EvalCaseDomain] = None,
    partition: Optional[DatasetPartition] = None,
    x_caller_role: str = Header(default="agent", alias="X-Caller-Role"),
) -> List[EvalCase]:
    """Lists cases from dataset.

    STRICT SECURITY GATE: Role 'agent' or untrusted callers are strictly forbidden from viewing SEALED_HOLDOUT.
    """
    try:
        cases = _dataset_mgr.list_cases(domain=domain, partition=partition, caller_role=x_caller_role)
        return cases
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/cases/{case_id}", response_model=EvalCase)
def get_case_by_id(
    case_id: str,
    x_caller_role: str = Header(default="agent", alias="X-Caller-Role"),
) -> EvalCase:
    """Gets single evaluation case with holdout role check."""
    try:
        return _dataset_mgr.get_case(case_id, caller_role=x_caller_role)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# 2. Run & Execution Endpoints
@router.post("/runs", response_model=EvalRunManifest)
def trigger_eval_run(
    req: TriggerRunRequest,
    x_caller_role: str = Header(default="eval_runner", alias="X-Caller-Role"),
) -> EvalRunManifest:
    """Executes an evaluation run over specified partition."""
    candidate = None
    if req.candidate_id:
        candidate = _store.get_candidate(req.candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail=f"Candidate {req.candidate_id} not found.")

    manifest, _ = _runner.run_eval_suite(
        eval_suite_id=req.eval_suite_id,
        partition=req.partition,
        candidate=candidate,
        baseline_snapshot_id=req.baseline_snapshot_id,
        caller_role=x_caller_role,
    )
    return manifest


@router.get("/runs/{run_id}", response_model=EvalRunManifest)
def get_eval_run(run_id: str) -> EvalRunManifest:
    """Retrieves manifest and summary metrics for an evaluation run."""
    run = _store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return run


@router.get("/runs/{run_id}/scores", response_model=List[ScoreResult])
def get_run_scores(run_id: str) -> List[ScoreResult]:
    """Retrieves all case scores and rationales for an evaluation run."""
    scores = _store.get_scores_for_run(run_id)
    return scores


# 3. Diagnosis & Proposal Endpoints
@router.post("/proposals/diagnose")
def diagnose_and_propose(req: DiagnoseRequest) -> Dict[str, Any]:
    """Clusters failures for a run and generates improvement proposals."""
    scores = _store.get_scores_for_run(req.run_id)
    if not scores:
        raise HTTPException(status_code=404, detail=f"No scores found for run {req.run_id}.")

    clusters = _proposal_engine.diagnose_failures(scores)
    pairs = _proposal_engine.generate_proposals(baseline_snapshot_id=req.run_id, failing_clusters=clusters)

    out_proposals = []
    out_candidates = []
    for prop, cand in pairs:
        _store.save_candidate(cand)
        out_proposals.append(prop.model_dump())
        out_candidates.append(cand.model_dump())

    return {
        "run_id": req.run_id,
        "diagnosed_clusters": [c.value for c in clusters.keys()],
        "proposals": out_proposals,
        "candidates": out_candidates,
    }


# 4. Candidates & Experiments Endpoints
@router.get("/candidates/{candidate_id}", response_model=CandidateChange)
def get_candidate(candidate_id: str) -> CandidateChange:
    """Retrieves candidate change details."""
    cand = _store.get_candidate(candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found.")
    return cand


@router.post("/experiments/matched", response_model=MatchedComparisonResult)
def run_matched_experiment(req: MatchedExperimentRequest) -> MatchedComparisonResult:
    """Runs matched experiment comparing baseline vs candidate on partition."""
    candidate = _store.get_candidate(req.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {req.candidate_id} not found.")

    res = _runner.run_matched_experiment(
        candidate=candidate,
        partition=req.partition,
        baseline_snapshot_id=req.baseline_snapshot_id,
    )
    return res


# 5. Promotion, Canary & Rollback Endpoints
@router.post("/candidates/{candidate_id}/promote", response_model=PromotionDecision)
def promote_candidate(candidate_id: str, req: PromotionRequest) -> PromotionDecision:
    """Evaluates promotion gates and promotes candidate to active deployment."""
    candidate = _store.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found.")

    # Run quick matched experiment on holdout to verify gates
    comp = _runner.run_matched_experiment(candidate=candidate, partition=DatasetPartition.SEALED_HOLDOUT)

    decision = _promotion_ctrl.evaluate_promotion_eligibility(
        candidate=candidate,
        comparison=comp,
        security_clean=req.security_clean,
        approval_token=req.approval_token,
        approver_id=req.approver_id,
    )
    return decision


@router.post("/candidates/{candidate_id}/canary")
def canary_stage(candidate_id: str, req: CanaryRequest) -> Dict[str, Any]:
    """Executes canary stage with anomaly detection."""
    candidate = _store.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found.")

    return _promotion_ctrl.execute_canary_stage(
        candidate=candidate,
        traffic_pct=req.traffic_pct,
        simulated_error_rate=req.simulated_error_rate,
    )


@router.post("/candidates/{candidate_id}/rollback", response_model=RollbackReceipt)
def rollback_candidate(candidate_id: str, req: RollbackRequest) -> RollbackReceipt:
    """Triggers instant rollback restoring verified baseline configuration hash."""
    receipt = _promotion_ctrl.execute_rollback(
        candidate_id=candidate_id,
        reason=req.reason,
        restored_by=req.restored_by,
    )
    return receipt


# 6. Leakage & Contamination Check
@router.post("/leakage/check", response_model=ContaminationCheckResult)
def check_contamination(req: LeakageCheckRequest) -> ContaminationCheckResult:
    """Checks input text or patch diff for contamination with sealed holdout items."""
    return _dataset_mgr.check_contamination(req.text, threshold_jaccard=req.threshold_jaccard)
