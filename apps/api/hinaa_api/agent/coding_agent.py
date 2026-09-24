"""C3 Self-Repairing Coding Agent Loop (Directives §16–§22).

Implements:
1. CodePatch with base hash verification to prevent clobbering concurrent edits.
2. Atomic patch application with AST syntax validation before disk write.
3. RepairAttempt history tracker preventing duplicate failed patches.
4. Failure parsing, neighborhood context retrieval, and iterative delta patching.
5. Deterministic verification gate before declaring task resolution.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ..repository.models import RepositoryMap, Symbol
from .repair import LoopDetector, RepairAction, RepairController
from .sandbox import (
    CommandRequest,
    CommandResult,
    ParsedExecutionOutput,
    PytestOutputParser,
    SandboxExecutor,
)
from .verifier_registry import (
    ClassifiedFailure,
    FailureCategory,
    FailureClassifier,
    VerificationOutcome,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


def compute_file_hash(content: str) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class CodePatch:
    file_path: str
    target_content: str
    replacement_content: str
    base_hash: str = ""
    allow_multiple: bool = False

    def patch_fingerprint(self) -> str:
        """Deterministic fingerprint for loop/duplicate detection."""
        norm_path = self.file_path.replace("\\", "/")
        return hashlib.sha256(
            f"{norm_path}:{self.target_content}->{self.replacement_content}".encode("utf-8")
        ).hexdigest()[:16]


@dataclass
class PatchResult:
    success: bool
    file_path: str
    diff: str = ""
    new_hash: str = ""
    error: str | None = None
    failure_category: FailureCategory | None = None


def apply_code_patch(
    root_path: str,
    patch: CodePatch,
    validate_syntax: bool = True,
) -> PatchResult:
    """Atomically applies CodePatch with base hash validation and AST syntax verification."""
    norm_root = os.path.realpath(os.path.abspath(root_path))
    full_path = os.path.realpath(os.path.abspath(os.path.join(norm_root, patch.file_path)))

    if not full_path.startswith(norm_root):
        return PatchResult(
            success=False,
            file_path=patch.file_path,
            error=f"File path {patch.file_path!r} escapes workspace root",
            failure_category=FailureCategory.GIT_PERMISSION_VIOLATION,
        )

    if not os.path.exists(full_path):
        return PatchResult(
            success=False,
            file_path=patch.file_path,
            error=f"Target file not found: {patch.file_path}",
            failure_category=FailureCategory.SYNTAX_ERROR,
        )

    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
        existing_content = f.read()

    # 1. Base Hash Verification (Prevents Concurrent Clobbering)
    current_hash = compute_file_hash(existing_content)
    if patch.base_hash and patch.base_hash.lower() != current_hash.lower():
        return PatchResult(
            success=False,
            file_path=patch.file_path,
            error=(
                f"Base hash mismatch for {patch.file_path}: expected {patch.base_hash[:8]}, "
                f"found {current_hash[:8]}. Concurrent edit detected; aborting clobber."
            ),
            failure_category=FailureCategory.CONCURRENT_EDIT,
        )

    # 2. Match Target Content
    if patch.target_content not in existing_content:
        return PatchResult(
            success=False,
            file_path=patch.file_path,
            error=f"Target content not found in {patch.file_path}",
            failure_category=FailureCategory.SYNTAX_ERROR,
        )

    if not patch.allow_multiple and existing_content.count(patch.target_content) > 1:
        return PatchResult(
            success=False,
            file_path=patch.file_path,
            error=f"Multiple occurrences ({existing_content.count(patch.target_content)}) of target content found; specify more unique context",
            failure_category=FailureCategory.SYNTAX_ERROR,
        )

    if patch.allow_multiple:
        new_content = existing_content.replace(patch.target_content, patch.replacement_content)
    else:
        new_content = existing_content.replace(patch.target_content, patch.replacement_content, 1)

    # 3. Syntax Verification (Before Disk Write)
    if validate_syntax and (full_path.endswith(".py") or patch.file_path.endswith(".py")):
        try:
            ast.parse(new_content, filename=patch.file_path)
        except SyntaxError as syn_err:
            return PatchResult(
                success=False,
                file_path=patch.file_path,
                error=f"Patch introduces Python syntax error: {syn_err}",
                failure_category=FailureCategory.SYNTAX_ERROR,
            )

    # 4. Atomic Write
    try:
        tmp_path = f"{full_path}.hinaa_tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp_path, full_path)
    except Exception as exc:
        return PatchResult(
            success=False,
            file_path=patch.file_path,
            error=f"Failed to write patched file: {exc}",
            failure_category=FailureCategory.COMMAND_FAILURE,
        )

    # 5. Compute Diff & New Hash
    diff_lines = list(
        difflib.unified_diff(
            existing_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{patch.file_path}",
            tofile=f"b/{patch.file_path}",
        )
    )
    diff_text = "".join(diff_lines)
    new_hash = compute_file_hash(new_content)

    return PatchResult(
        success=True,
        file_path=patch.file_path,
        diff=diff_text,
        new_hash=new_hash,
    )


@dataclass
class RepairAttempt:
    attempt_index: int
    patch: CodePatch
    patch_result: PatchResult
    test_output: str = ""
    parsed_failure: ParsedExecutionOutput | None = None
    classified: ClassifiedFailure | None = None


@dataclass
class CodingLoopResult:
    success: bool
    status: str  # "resolved", "budget_exhausted", "concurrent_edit_conflict", "syntax_failure"
    attempts: int
    history: list[RepairAttempt] = field(default_factory=list)
    applied_patches: list[CodePatch] = field(default_factory=list)
    final_test_output: str = ""
    evidence: list[str] = field(default_factory=list)
    error: str | None = None


class CodingAgentLoop:
    """Autonomous self-repairing coding agent loop.

    Flow:
    1. Generates or receives initial patch proposal.
    2. Applies patch atomically (verifying base hash & syntax).
    3. Executes targeted test suite in Sandbox.
    4. If test passes -> verifies completion evidence and completes.
    5. If test fails -> parses failure, classifies root cause, retrieves symbol neighborhood,
       synthesizes delta patch, and re-tests up to max_repair_attempts.
    """

    def __init__(
        self,
        workspace_root: str,
        sandbox: SandboxExecutor,
        repository_map: RepositoryMap | None = None,
        max_repair_attempts: int = 3,
    ) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.sandbox = sandbox
        self.repository_map = repository_map
        self.max_repair_attempts = max_repair_attempts
        self.classifier = FailureClassifier()
        self.repair_controller = RepairController()
        self.loop_detector = LoopDetector(window=8, threshold=2)

    def retrieve_error_context(self, failure_item: Any) -> str:
        """Retrieves neighborhood source snippets (±8 lines) for failure location."""
        loc = getattr(failure_item, "location", str(failure_item))
        file_path = loc.split("::")[0].split(":")[0]
        line_num = 0
        if ":" in loc:
            try:
                parts = loc.split(":")
                if len(parts) > 1 and parts[1].isdigit():
                    line_num = int(parts[1])
            except Exception:
                pass

        full_path = os.path.join(self.workspace_root, file_path)
        if not os.path.exists(full_path):
            return f"Source context for {file_path} not found on disk"

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            if line_num > 0:
                start = max(0, line_num - 8)
                end = min(len(lines), line_num + 8)
                snippet_lines = [
                    f"{idx + 1:4d}: {lines[idx]}"
                    for idx in range(start, end)
                ]
                return f"File: {file_path} (lines {start + 1}-{end}):\n" + "".join(snippet_lines)
            else:
                # Return first 30 lines
                return f"File: {file_path}:\n" + "".join(lines[:30])
        except Exception as exc:
            return f"Error reading source snippet: {exc}"

    async def execute_repair_loop(
        self,
        patch_generator: Callable[[int, str, RepairAttempt | None], Awaitable[CodePatch]],
        test_command: list[str] | str,
        *,
        timeout_seconds: float = 60.0,
    ) -> CodingLoopResult:
        history: list[RepairAttempt] = []
        applied_patches: list[CodePatch] = []
        last_attempt: RepairAttempt | None = None
        evidence: list[str] = []

        seen_fingerprints: set[str] = set()

        for attempt_idx in range(self.max_repair_attempts):
            error_context = ""
            if last_attempt and last_attempt.parsed_failure and last_attempt.parsed_failure.failures:
                error_context = self.retrieve_error_context(last_attempt.parsed_failure.failures[0])

            # 1. Generate patch
            patch = await patch_generator(attempt_idx, error_context, last_attempt)
            fingerprint = patch.patch_fingerprint()

            if fingerprint in seen_fingerprints:
                return CodingLoopResult(
                    success=False,
                    status="budget_exhausted",
                    attempts=attempt_idx + 1,
                    history=history,
                    applied_patches=applied_patches,
                    evidence=evidence,
                    error=f"Loop detected: duplicate patch proposed for {patch.file_path}",
                )
            seen_fingerprints.add(fingerprint)

            # 2. Apply patch
            patch_res = apply_code_patch(self.workspace_root, patch, validate_syntax=True)
            if not patch_res.success:
                attempt = RepairAttempt(
                    attempt_index=attempt_idx,
                    patch=patch,
                    patch_result=patch_res,
                )
                history.append(attempt)
                if patch_res.failure_category == FailureCategory.CONCURRENT_EDIT:
                    return CodingLoopResult(
                        success=False,
                        status="concurrent_edit_conflict",
                        attempts=attempt_idx + 1,
                        history=history,
                        applied_patches=applied_patches,
                        evidence=evidence,
                        error=patch_res.error,
                    )
                # Retry next attempt
                last_attempt = attempt
                continue

            applied_patches.append(patch)
            evidence.append(f"Applied patch on {patch.file_path} (new hash: {patch_res.new_hash[:8]})")

            # 3. Run Test Command in Sandbox
            cmd_res = await self.sandbox.run_command(
                CommandRequest(
                    command=test_command,
                    cwd=self.workspace_root,
                    allowed_root=self.workspace_root,
                    timeout_seconds=timeout_seconds,
                )
            )

            # 4. Check Test Result
            if cmd_res.success:
                evidence.append(f"Test command succeeded with exit code 0 ({cmd_res.duration_ms:.1f}ms)")
                return CodingLoopResult(
                    success=True,
                    status="resolved",
                    attempts=attempt_idx + 1,
                    history=history,
                    applied_patches=applied_patches,
                    final_test_output=cmd_res.stdout,
                    evidence=evidence,
                )

            # 5. Parse Test Failure
            combined_output = f"{cmd_res.stdout}\n{cmd_res.stderr}"
            parsed = PytestOutputParser.parse(combined_output)

            # Classify Failure
            outcome = VerificationOutcome(
                status=VerificationStatus.FAIL,
                verifier_id="builtin.code_test",
                message=parsed.raw_summary or f"Test exited with {cmd_res.exit_code}",
                evidence=[combined_output[:500]],
            )
            classified = self.classifier.classify(outcome, skill_id="coding_test", attempt=attempt_idx)

            attempt = RepairAttempt(
                attempt_index=attempt_idx,
                patch=patch,
                patch_result=patch_res,
                test_output=combined_output,
                parsed_failure=parsed,
                classified=classified,
            )
            history.append(attempt)
            last_attempt = attempt
            evidence.append(f"Attempt {attempt_idx + 1} failed: {outcome.message}")

        # Budget exhausted
        return CodingLoopResult(
            success=False,
            status="budget_exhausted",
            attempts=self.max_repair_attempts,
            history=history,
            applied_patches=applied_patches,
            final_test_output=last_attempt.test_output if last_attempt else "",
            evidence=evidence,
            error=f"Exhausted {self.max_repair_attempts} repair attempts without test resolution",
        )
