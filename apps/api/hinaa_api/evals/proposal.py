"""HINAA OS — Phase 16 Diagnostic & Adaptive Proposal Engine.

Analyzes evaluation trace failures, diagnoses root causes across a 10-category failure taxonomy,
and generates structured, bounded improvement proposals across targeted modification layers:
- Prompts, examples, retrieval tuning, routing rules, tool definitions, policies.
- Enforces strict boundaries: weights_updated=False, blast radius containment, no PDP tampering.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Dict, List, Optional, Set, Tuple

from hinaa_api.evals.contracts import (
    CandidateChange,
    CandidateStatus,
    FailureCluster,
    ImprovementProposal,
    ScoreResult,
)


class DiagnosticProposalEngine:
    """Diagnoses evaluation failures and generates safe, bounded improvement proposals."""

    FORBIDDEN_MUTATION_PATHS = {
        "apps/api/hinaa_api/security/pdp.py",
        "apps/api/hinaa_api/security/audit.py",
        "apps/api/hinaa_api/security/crypto.py",
        "apps/api/hinaa_api/billing/",
        "apps/api/hinaa_api/evals/store.py",
        "apps/api/hinaa_api/evals/promotion.py",
    }

    def __init__(self, max_iterations: int = 3) -> None:
        self.max_iterations = max_iterations

    def diagnose_failures(self, scores: List[ScoreResult]) -> Dict[FailureCluster, List[ScoreResult]]:
        """Clusters failing score results into reproducible failure taxonomy categories."""
        clusters: Dict[FailureCluster, List[ScoreResult]] = {c: [] for c in FailureCluster}

        for s in scores:
            if s.passed:
                continue

            rationale = (s.details.get("rationale") or "").lower()
            scorer_type = s.details.get("scorer_type", "")

            if "fabricated citation" in rationale or scorer_type == "citation_groundedness":
                clusters[FailureCluster.CITATION_MISMATCH].append(s)
            elif "spoken words" in rationale or "words/" in rationale or "brevity" in rationale:
                clusters[FailureCluster.EXCESSIVE_VERBOSITY].append(s)
            elif "nepali" in rationale or "devanagari" in rationale or "romanized" in rationale:
                clusters[FailureCluster.NEPALI_MISTRANSLATION].append(s)
            elif "timeout" in rationale or "timed out" in rationale:
                clusters[FailureCluster.TIMEOUT].append(s)
            elif "permission" in rationale or "security" in rationale or "pdp" in rationale:
                clusters[FailureCluster.PERMISSION_FAILURE].append(s)
            elif "tool" in rationale or "wrong tool" in rationale:
                clusters[FailureCluster.WRONG_TOOL].append(s)
            elif "memory" in rationale or "stale" in rationale or "entity" in rationale:
                clusters[FailureCluster.STALE_MEMORY].append(s)
            elif "audio" in rationale or "ssml" in rationale:
                clusters[FailureCluster.AUDIO_DUPLICATION].append(s)
            elif "unsupported" in rationale:
                clusters[FailureCluster.UNSUPPORTED_CAPABILITY].append(s)
            else:
                clusters[FailureCluster.REASONING_ERROR].append(s)

        # Filter out empty clusters
        return {cluster: items for cluster, items in clusters.items() if items}

    def generate_proposals(
        self,
        baseline_snapshot_id: str,
        failing_clusters: Dict[FailureCluster, List[ScoreResult]],
    ) -> List[Tuple[ImprovementProposal, CandidateChange]]:
        """Formulates targeted candidate changes to address identified failure clusters."""
        proposals_and_candidates = []

        for cluster, failing_scores in failing_clusters.items():
            evidence_ids = [s.score_id for s in failing_scores]
            proposal_id = f"prop-{uuid.uuid4().hex[:12]}"
            candidate_id = f"cand-{uuid.uuid4().hex[:12]}"

            target_layer, patch_diff, file_path, rationale = self._synthesize_candidate_change(
                cluster, failing_scores
            )

            # Security sanity check on candidate target path
            is_forbidden = any(f in (file_path or "") for f in self.FORBIDDEN_MUTATION_PATHS)
            status = CandidateStatus.REJECTED if is_forbidden else CandidateStatus.PROPOSED

            config_hash_before = hashlib.sha256(f"baseline:{baseline_snapshot_id}".encode()).hexdigest()
            config_hash_after = hashlib.sha256(f"{config_hash_before}:{patch_diff}".encode()).hexdigest()

            candidate = CandidateChange(
                candidate_id=candidate_id,
                proposal_id=proposal_id,
                target_layer=target_layer,
                description=rationale if not is_forbidden else "REJECTED: Unauthorized attempt to mutate protected security/governance infrastructure.",
                patch_diff=patch_diff,
                config_hash_before=config_hash_before,
                config_hash_after=config_hash_after,
                weights_updated=False,  # Explicit: No model fine-tuning weights altered
                status=status,
                created_at=time.time(),
            )

            blast_radius = min(1.0, len(failing_scores) / 240.0 * 2.0)

            proposal = ImprovementProposal(
                proposal_id=proposal_id,
                symptom=f"Cluster {cluster.value} with {len(failing_scores)} failing cases.",
                failure_cluster=cluster,
                evidence_trace_ids=evidence_ids,
                patch_scope=file_path,
                expected_metric="accuracy",
                target_threshold=0.85,
                blast_radius=f"{round(blast_radius, 3)}",
                authorization_tier="Tier C" if is_forbidden else "Tier B",
                baseline_snapshot_id=baseline_snapshot_id,
                created_at=time.time(),
            )
            proposals_and_candidates.append((proposal, candidate))

        return proposals_and_candidates[: self.max_iterations]

    def _synthesize_candidate_change(
        self,
        cluster: FailureCluster,
        scores: List[ScoreResult],
    ) -> Tuple[str, str, str, str]:
        """Synthesizes structured diff or configuration content based on failure diagnosis."""
        if cluster == FailureCluster.CITATION_MISMATCH:
            return (
                "prompt",
                "Add explicit citation grounding directive: 'Cite ONLY sources present in provided context. Do NOT invent references or use ungrounded bracket tags.'",
                "apps/api/hinaa_api/prompts/research_system.txt",
                "Eliminate fabricated bracket citations like [999] by strictly binding generation to context sources.",
            )
        elif cluster == FailureCluster.EXCESSIVE_VERBOSITY:
            return (
                "prompt",
                "Update spoken brevity constraint: 'Keep spoken voice summaries under 45 words strictly, retaining only cause and resolution.'",
                "apps/api/hinaa_api/prompts/voice_reflective.txt",
                "Enforce brevity ratio to reduce spoken word count below maximum latency and user attention limits.",
            )
        elif cluster == FailureCluster.NEPALI_MISTRANSLATION:
            return (
                "examples",
                "Add few-shot bilingual pairs: 'कस्टमर सेवा: तपाईंको सामान डेलिभरीमा भएको ढिलाइको लागि क्षमाप्रार्थी छौँ।' and honorific distinction notes.",
                "apps/api/hinaa_api/prompts/bilingual_fewshots.json",
                "Improve respectful formal Devanagari translation fidelity and cultural honorific usage.",
            )
        elif cluster == FailureCluster.WRONG_TOOL:
            return (
                "tool_definitions",
                "Clarify tool schema descriptions for file sandboxing and database querying parameters to prevent misrouting.",
                "apps/api/hinaa_api/tools/registry.json",
                "Improve tool parameter documentation to guide router toward correct specialized endpoints.",
            )
        elif cluster == FailureCluster.STALE_MEMORY:
            return (
                "retrieval",
                "Update temporal memory query parameter: set recency_decay_lambda=0.05 and boost updated_at timestamps.",
                "apps/api/hinaa_api/memory/config.json",
                "Favor recent temporal entity state updates over superseded historical statements.",
            )
        elif cluster == FailureCluster.PERMISSION_FAILURE:
            return (
                "routing",
                "Ensure high-impact tool invocations route through PDP Tier C human-in-the-loop authorization gates.",
                "apps/api/hinaa_api/security/routing_rules.json",
                "Eliminate unauthorized bypass attempts and cleanly surface permission requirement tokens.",
            )
        else:
            return (
                "prompt",
                "Inject Chain-of-Thought reasoning scaffolding: 'Think step-by-step before stating the final answer.'",
                "apps/api/hinaa_api/prompts/reasoning_cot.txt",
                "Enhance multi-step deductive and probabilistic reasoning through structured CoT scaffolding.",
            )
