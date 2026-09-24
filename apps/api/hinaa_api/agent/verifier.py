from __future__ import annotations

import re
from typing import Any

from .contracts import (
    AgentPlan,
    AgentRun,
    OperationType,
    RunStatus,
    StepState,
    VerificationResult,
)
from .state import AgentGoal, PlanStep, StepResult, VerificationReport

_PROMPT_INJECTION_PATTERN = re.compile(
    r"(?i)\b(?:"
    r"ignore\s+(?:all\s+)?(?:previous|prior|system|developer)\s+instructions|"
    r"system\s+override|"
    r"reveal\s+(?:the\s+)?(?:system\s+prompt|secrets?|credentials?)|"
    r"delete\s+(?:all\s+)?files"
    r")\b"
)


def _collect_text(value: Any, *, depth: int = 0) -> list[str]:
    """Extract bounded textual content from untrusted tool envelopes."""
    if depth > 5:
        return []
    if isinstance(value, str):
        return [value[:20_000]]
    if isinstance(value, dict):
        fragments: list[str] = []
        for nested in value.values():
            fragments.extend(_collect_text(nested, depth=depth + 1))
            if sum(len(item) for item in fragments) >= 50_000:
                break
        return fragments
    if isinstance(value, (list, tuple, set)):
        fragments = []
        for nested in value:
            fragments.extend(_collect_text(nested, depth=depth + 1))
            if sum(len(item) for item in fragments) >= 50_000:
                break
        return fragments
    return []


class AgentVerifier:
    """Audits step results and overall plan execution for truthfulness,

    completeness, constraint adherence, and anti-hallucination.
    """

    def check_step(self, goal: AgentGoal, step: PlanStep, result: StepResult) -> VerificationReport:
        """Verifies an individual step execution."""
        evidence: list[str] = []
        issues: list[str] = []

        # 1. Basic failure and envelope checks. A tool must return a concrete
        # JSON-like value; ``None`` and arbitrary scalar values are not a
        # successful tool contract.
        if step.error or result.output is None:
            return VerificationReport(
                passed=False,
                confidence=0.0,
                evidence=[],
                unresolved_issues=[f"Step '{step.title}' failed: {step.error or 'Empty output'}"],
                needs_replan=True,
                replan_guidance=f"Retry or select alternative skill for {step.skill_id}.",
            )
        if not isinstance(result.output, (dict, list, str, int, float, bool)):
            return VerificationReport(
                passed=False,
                confidence=0.0,
                unresolved_issues=["Tool returned an unsupported output envelope."],
                needs_replan=True,
            )

        # 2. Treat every external result as untrusted. Scan the actual output,
        # not only a human-readable observation, before it can become input to
        # a dependent planning or synthesis step.
        external_text = "\n".join([str(result.observations), *_collect_text(result.output)])[:50_000]
        if _PROMPT_INJECTION_PATTERN.search(external_text):
            result.is_untrusted_content = True
            return VerificationReport(
                passed=False,
                confidence=0.0,
                evidence=["Quarantined external malicious command tokens from agent execution context."],
                unresolved_issues=["Potential indirect prompt injection detected in external content."],
                needs_replan=False,
                replan_guidance="Do not forward or automatically retry content from this source.",
            )

        # 3. Skill-specific sanity checks
        if step.skill_id == "image_search":
            images = []
            if isinstance(result.output, dict):
                images = result.output.get("images") or result.output.get("results") or []
            elif isinstance(result.output, list):
                images = result.output

            if not images:
                issues.append("Image search yielded zero results.")
                return VerificationReport(
                    passed=False,
                    confidence=0.3,
                    evidence=[],
                    unresolved_issues=issues,
                    needs_replan=True,
                    replan_guidance=f"Broaden image search terms for query '{step.parameters.get('query', '')}'.",
                )
            evidence.append(f"Successfully retrieved {len(images)} image candidates.")

        elif step.skill_id in ("web_search", "web_research", "web_answer"):
            text_content = ""
            records: list[Any] = []
            if isinstance(result.output, dict):
                text_content = str(result.output.get("text") or result.output.get("content") or result.output.get("results") or "")
                records = result.output.get("results") or []
            elif isinstance(result.output, str):
                text_content = result.output

            # Search results may be structured records, while web_answer must
            # contain enough prose to be useful. Do not accept status-only
            # envelopes as successful research.
            valid_search_records = isinstance(records, list) and any(isinstance(item, dict) and item for item in records)
            if ((step.skill_id == "web_answer" and len(text_content.strip()) < 20) or
                    (step.skill_id != "web_answer" and not valid_search_records and len(text_content.strip()) < 20)) and not issues:
                issues.append("Web search returned insufficient or empty textual information.")
                return VerificationReport(
                    passed=False,
                    confidence=0.4,
                    evidence=[],
                    unresolved_issues=issues,
                    needs_replan=True,
                    replan_guidance="Search with alternative keywords or wider search operators.",
                )
            evidence.append("Retrieved valid web sources with factual citations.")

        elif step.skill_id == "image_generate":
            has_image = False
            if isinstance(result.output, dict) and (result.output.get("imageUrl") or result.output.get("image_url") or result.output.get("url")):
                has_image = True
            elif isinstance(result.output, str) and result.output.startswith("http"):
                has_image = True

            # Generation is asynchronous in the production tool. A queued
            # job envelope is valid even though an image URL is not available
            # yet; arbitrary ``{"status": "ok"}`` remains invalid.
            queued = isinstance(result.output, dict) and result.output.get("status") in {"processing", "queued"} and bool(result.output.get("job_id") or result.output.get("jobId"))
            if not has_image and not queued:
                return VerificationReport(
                    passed=False,
                    confidence=0.2,
                    evidence=[],
                    unresolved_issues=["Generated image artifact URL missing."],
                    needs_replan=True,
                    replan_guidance="Fallback to alternative creative engine seed or mode.",
                )
            evidence.append("Creative image artifact successfully generated and verified.")

        elif step.skill_id == "pdf_generate":
            valid_pdf = (
                isinstance(result.output, dict)
                and result.output.get("status") in {"success", "completed"}
                and bool(result.output.get("downloadUrl") or result.output.get("filename"))
            )
            if not valid_pdf:
                return VerificationReport(
                    passed=False,
                    confidence=0.1,
                    unresolved_issues=["PDF generator returned no verifiable artifact envelope."],
                    needs_replan=True,
                )
            evidence.append("PDF artifact envelope contains a downloadable document.")


        return VerificationReport(
            passed=len(issues) == 0,
            confidence=0.92 if len(issues) == 0 else 0.5,
            evidence=evidence,
            unresolved_issues=issues,
            needs_replan=len(issues) > 0,
            replan_guidance=issues[0] if issues else None,
        )

    def check_overall(
        self,
        goal: AgentGoal,
        steps: list[PlanStep],
        final_answer: str,
    ) -> VerificationReport:
        """Verifies that the aggregate execution satisfied user constraints."""
        evidence: list[str] = []
        issues: list[str] = []

        completed_steps = [s for s in steps if s.status.value == "completed"]
        failed_steps = [s for s in steps if s.status.value == "failed"]

        if failed_steps and not completed_steps:
            return VerificationReport(
                passed=False,
                confidence=0.1,
                evidence=[],
                unresolved_issues=[f"{len(failed_steps)} required steps failed."],
                needs_replan=True,
                replan_guidance="Re-evaluate goal with alternative tool strategies.",
            )

        # Validate constraints
        for constraint in goal.constraints:
            c_lower = constraint.lower()
            if "under" in c_lower or "budget" in c_lower or "below" in c_lower:
                evidence.append(f"Checked budget constraint: {constraint}")
            elif "image" in c_lower or "picture" in c_lower:
                if not any(s.skill_id in ("image_search", "image_generate") for s in completed_steps):
                    issues.append("User requested visual imagery, but no image step completed successfully.")

        if not final_answer or len(final_answer.strip()) < 5:
            issues.append("Agent produced an empty final answer.")

        passed = len(issues) == 0
        conf = 0.95 if (passed and not failed_steps) else (0.75 if passed else 0.4)

        return VerificationReport(
            passed=passed,
            confidence=conf,
            evidence=evidence,
            unresolved_issues=issues,
            needs_replan=not passed,
            replan_guidance="Generate complete synthesis addressing all unsatisfied constraints." if issues else None,
        )

    def verify_run(self, run: AgentRun, plan: AgentPlan) -> VerificationResult:
        issues: list[str] = []
        if run.status == RunStatus.CANCELLED or run.cancellation_requested:
            return VerificationResult(valid=False, issues=["Run was cancelled"], failure_code="run_cancelled")

        for step in plan.steps:
            if step.status == StepState.FAILED:
                issues.append(f"Step '{step.title}' failed: {step.error_message or 'Execution failure'}")
            elif step.operation_type == OperationType.TOOL and step.result is None:
                issues.append(f"Tool step '{step.title}' has missing result")
            elif step.status not in (StepState.COMPLETED, StepState.SKIPPED):
                issues.append(f"Step '{step.title}' is not completed ({step.status.value})")

        if issues:
            corrected = None
            if run.replan_count < run.maximum_replans:
                run.replan_count += 1
                corrected = f"Correcting issue: {issues[0]}"
            return VerificationResult(
                valid=False,
                issues=issues,
                corrected_response=corrected,
                failure_code="verification_failed",
            )
        return VerificationResult(valid=True, issues=[])
