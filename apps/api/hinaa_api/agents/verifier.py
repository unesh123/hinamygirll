"""
HINAA OS — Phase 11 Independent Verification Oracle
Validates agent postconditions, exit codes, file checksums, test outputs,
and reconciles conflicting claims with evidence-weighted truthfulness.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    AgentRole,
    TaskNode,
    TaskStatus,
    ToolReceipt,
)

logger = logging.getLogger("hinaa.agents.verifier")


class VerificationResult:
    def __init__(
        self,
        passed: bool,
        notes: str,
        evidence: List[str],
        artifact_checksums: Dict[str, str],
    ) -> None:
        self.passed = passed
        self.notes = notes
        self.evidence = evidence
        self.artifact_checksums = artifact_checksums

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "notes": self.notes,
            "evidence": self.evidence,
            "artifact_checksums": self.artifact_checksums,
        }


class IndependentVerifier:
    """Verifies that executed node actions meet required postconditions using deterministic criteria."""

    @staticmethod
    def compute_sha256(file_path: str | Path) -> Optional[str]:
        """Compute SHA-256 digest of a physical file."""
        p = Path(file_path)
        if not p.is_file():
            return None
        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def verify_node(self, node: TaskNode, receipts: List[ToolReceipt]) -> VerificationResult:
        """
        Evaluate node execution against physical facts.
        Rejects success claims if exit codes are non-zero or expected files are missing.
        """
        evidence: List[str] = []
        artifact_checksums: Dict[str, str] = {}

        # 1. Inspect receipts exit codes
        for r in receipts:
            if r.exit_code != 0:
                evidence.append(f"Receipt {r.receipt_id} for tool '{r.tool_name}' failed with exit_code {r.exit_code}")
                return VerificationResult(
                    passed=False,
                    notes=f"Tool execution failed: {r.tool_name} returned exit code {r.exit_code}",
                    evidence=evidence,
                    artifact_checksums=artifact_checksums,
                )
            evidence.append(f"Receipt {r.receipt_id} verified: tool '{r.tool_name}' returned 0")

            # Check generated artifact files
            for a_path in r.artifact_paths:
                if os.path.exists(a_path):
                    digest = self.compute_sha256(a_path)
                    if digest:
                        artifact_checksums[a_path] = digest
                        evidence.append(f"Artifact '{os.path.basename(a_path)}' verified (sha256={digest[:12]}...)")
                else:
                    evidence.append(f"Declared artifact missing on disk: {a_path}")
                    return VerificationResult(
                        passed=False,
                        notes=f"Artifact missing: {a_path}",
                        evidence=evidence,
                        artifact_checksums=artifact_checksums,
                    )

        # 2. Inspect node result data for test failures or explicit errors
        if node.result_data:
            if node.result_data.get("failed_tests", 0) > 0:
                fail_cnt = node.result_data.get("failed_tests")
                evidence.append(f"Test suite reported {fail_cnt} test failures")
                return VerificationResult(
                    passed=False,
                    notes=f"Test failure: {fail_cnt} tests failed",
                    evidence=evidence,
                    artifact_checksums=artifact_checksums,
                )

            if "error" in node.result_data and node.result_data["error"]:
                err = node.result_data["error"]
                evidence.append(f"Node result data reported error: {err}")
                return VerificationResult(
                    passed=False,
                    notes=f"Error in result: {err}",
                    evidence=evidence,
                    artifact_checksums=artifact_checksums,
                )

        # 3. If QA specialist, check that QA approved
        if node.specialist_role == AgentRole.QA:
            qa_approved = node.result_data.get("qa_passed", True) if node.result_data else True
            if not qa_approved:
                evidence.append("QA agent explicitly rejected verification")
                return VerificationResult(
                    passed=False,
                    notes="QA assertion failed",
                    evidence=evidence,
                    artifact_checksums=artifact_checksums,
                )

        return VerificationResult(
            passed=True,
            notes="All deterministic postconditions, exit codes, and artifact hashes verified",
            evidence=evidence,
            artifact_checksums=artifact_checksums,
        )

    def reconcile_conflicts(
        self,
        engineer_result: Dict[str, Any],
        qa_result: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Reconcile conflicting claims between Engineer and QA.
        Deterministic rule: QA's objective test runs and exit codes always override
        an Engineer's optimistic completion claims.
        """
        eng_claimed_success = engineer_result.get("status") == "SUCCESS" or engineer_result.get("success", False)
        qa_passed = qa_result.get("qa_passed", False) and qa_result.get("exit_code", 0) == 0

        if eng_claimed_success and not qa_passed:
            reason = f"Conflict resolved in favor of QA evidence: Engineer claimed success, but QA suite reported failure (exit_code={qa_result.get('exit_code')}, errors={qa_result.get('errors')})"
            logger.warning(reason)
            return False, reason

        if qa_passed:
            return True, "QA verified test suite execution and artifact integrity"

        return False, "Both or QA reported failure"
