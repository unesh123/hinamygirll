"""
HINAA OS — Phase 14: Independent Milestone Critic & Receipt Verifier (Module C)
Evaluates milestone execution based on verifiable proof (tool receipts, test exit codes,
output hashes, browser snapshots, and source provenance) rather than agent text claims.
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    EvidenceReceipt,
    Milestone,
    MilestoneStatus,
)


class MilestoneCritic:
    """Rigorous independent assessor of milestone outcomes."""

    def evaluate_milestone(
        self,
        milestone: Milestone,
        receipts: List[EvidenceReceipt],
    ) -> Tuple[MilestoneStatus, str]:
        """
        Evaluates whether a milestone satisfies its exit criteria based on receipts.
        Returns (status, justification).
        """
        if not receipts:
            # If no receipts exist, a claim of completion cannot be accepted
            return (
                MilestoneStatus.UNVERIFIED,
                "Milestone claimed completed but no verifiable tool receipts or evidence hashes were provided."
            )

        # 1. Check for test exit code failures
        for r in receipts:
            if r.exit_code != 0:
                return (
                    MilestoneStatus.FAILED,
                    f"Execution failed in tool '{r.tool_name}' with non-zero exit code {r.exit_code}: {r.raw_snippet or 'Check test logs'}"
                )

        # 2. Check for missing required artifacts
        if "file_manifest" in milestone.evidence_requirements or "source_diff" in milestone.evidence_requirements:
            for r in receipts:
                prov = r.source_provenance
                target_file = prov.get("target_path") or prov.get("file_path")
                if target_file and not os.path.exists(target_file):
                    return (
                        MilestoneStatus.FAILED,
                        f"Claimed file '{target_file}' does not exist on disk."
                    )

        # 3. Check for contradictory evidence in research tasks
        for r in receipts:
            contradictions = r.source_provenance.get("contradictions", [])
            if contradictions:
                return (
                    MilestoneStatus.PARTIAL,
                    f"Contradictory findings detected across sources: {'; '.join(contradictions[:2])}"
                )

        # 4. Check for invalid or forged signatures
        for r in receipts:
            if not r.is_valid:
                return (
                    MilestoneStatus.FAILED,
                    f"Evidence receipt '{r.receipt_id}' failed authenticity / cryptographic verification."
                )

        # All checks passed
        return (
            MilestoneStatus.VERIFIED,
            f"All {len(receipts)} evidence receipts satisfied exit criteria with valid exit codes and provenance."
        )
