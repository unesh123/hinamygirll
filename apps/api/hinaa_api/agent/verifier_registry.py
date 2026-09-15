"""Phase 13 — Verification Engine: VerifierRegistry + FailureClassifier.

Design principles:
- Every verifier is a pure function ``(step_result, context) -> VerificationOutcome``.
- VerifierRegistry maps skill_id globs to ordered verifier chains.
- FailureClassifier converts raw failures into a typed ``FailureCategory`` so the
  RepairController can pick an appropriate repair strategy without heuristics.
- No LLM calls inside the verification layer — deterministic only.
"""
from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Outcome types
# ---------------------------------------------------------------------------

class VerificationStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"       # non-fatal; surfaced in audit but execution continues
    FAIL = "fail"       # fatal; triggers repair
    QUARANTINE = "quarantine"  # security violation; no retry


@dataclass(frozen=True)
class VerificationOutcome:
    status: VerificationStatus
    verifier_id: str
    message: str
    evidence: list[str] = field(default_factory=list)
    repair_hint: str | None = None   # consumed by RepairController
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status in (VerificationStatus.PASS, VerificationStatus.WARN)

    @property
    def is_fatal(self) -> bool:
        return self.status in (VerificationStatus.FAIL, VerificationStatus.QUARANTINE)


# ---------------------------------------------------------------------------
# Verifier protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class Verifier(Protocol):
    """A verifier is a callable that takes step output + context and returns an outcome."""

    verifier_id: str

    def __call__(
        self,
        result: Any,
        *,
        context: dict[str, Any] | None = None,
    ) -> VerificationOutcome:
        ...


# ---------------------------------------------------------------------------
# Built-in verifiers (used by default chains)
# ---------------------------------------------------------------------------

class _NonEmptyVerifier:
    verifier_id = "builtin.non_empty"

    def __call__(self, result: Any, *, context: dict[str, Any] | None = None) -> VerificationOutcome:
        if result is None:
            return VerificationOutcome(
                status=VerificationStatus.FAIL,
                verifier_id=self.verifier_id,
                message="Step returned None",
                repair_hint="retry_step",
            )
        if isinstance(result, (str, list, dict)) and len(result) == 0:
            return VerificationOutcome(
                status=VerificationStatus.FAIL,
                verifier_id=self.verifier_id,
                message="Step returned empty value",
                repair_hint="retry_with_broader_params",
            )
        return VerificationOutcome(
            status=VerificationStatus.PASS,
            verifier_id=self.verifier_id,
            message="Result is non-empty",
        )


class _RequiredKeysVerifier:
    verifier_id = "builtin.required_keys"

    def __init__(self, required_keys: list[str]) -> None:
        self._required = required_keys

    def __call__(self, result: Any, *, context: dict[str, Any] | None = None) -> VerificationOutcome:
        if not isinstance(result, dict):
            return VerificationOutcome(
                status=VerificationStatus.FAIL,
                verifier_id=self.verifier_id,
                message=f"Expected dict, got {type(result).__name__}",
                repair_hint="retry_step",
            )
        missing = [k for k in self._required if k not in result]
        if missing:
            return VerificationOutcome(
                status=VerificationStatus.FAIL,
                verifier_id=self.verifier_id,
                message=f"Missing required keys: {missing}",
                repair_hint="retry_step",
            )
        return VerificationOutcome(
            status=VerificationStatus.PASS,
            verifier_id=self.verifier_id,
            message=f"All required keys present: {self._required}",
        )


class _CommandSuccessVerifier:
    verifier_id = "builtin.command_success"

    def __call__(self, result: Any, *, context: dict[str, Any] | None = None) -> VerificationOutcome:
        if isinstance(result, dict):
            code = result.get("exit_code", result.get("returncode", 0))
            if isinstance(code, int) and code != 0:
                stderr = str(result.get("stderr", ""))[:200]
                return VerificationOutcome(
                    status=VerificationStatus.FAIL,
                    verifier_id=self.verifier_id,
                    message=f"Command exited with code {code}: {stderr}",
                    repair_hint="retry_step",
                )
        return VerificationOutcome(
            status=VerificationStatus.PASS,
            verifier_id=self.verifier_id,
            message="Command succeeded",
        )


class _ArtifactPresenceVerifier:
    verifier_id = "builtin.artifact_presence"

    def __call__(self, result: Any, *, context: dict[str, Any] | None = None) -> VerificationOutcome:
        if isinstance(result, dict):
            arts = result.get("artifacts") or []
            if not arts:
                return VerificationOutcome(
                    status=VerificationStatus.FAIL,
                    verifier_id=self.verifier_id,
                    message="No artifacts produced",
                    repair_hint="retry_step",
                )
        return VerificationOutcome(
            status=VerificationStatus.PASS,
            verifier_id=self.verifier_id,
            message="Artifact presence confirmed",
        )


class _ImageResultVerifier:
    verifier_id = "builtin.image_result"

    def __call__(self, result: Any, *, context: dict[str, Any] | None = None) -> VerificationOutcome:
        if isinstance(result, dict):
            images = result.get("images") or result.get("results") or []
            if images:
                return VerificationOutcome(
                    status=VerificationStatus.PASS,
                    verifier_id=self.verifier_id,
                    message=f"Retrieved {len(images)} image(s)",
                    evidence=[f"image_count={len(images)}"],
                )
            url = result.get("imageUrl") or result.get("image_url") or result.get("url")
            queued = result.get("status") in {"processing", "queued"} and bool(result.get("job_id") or result.get("jobId"))
            if url or queued:
                return VerificationOutcome(
                    status=VerificationStatus.PASS,
                    verifier_id=self.verifier_id,
                    message="Image URL or queued job present",
                )
        return VerificationOutcome(
            status=VerificationStatus.FAIL,
            verifier_id=self.verifier_id,
            message="No image URL or results returned",
            repair_hint="retry_with_broader_params",
        )


class _WebSearchVerifier:
    verifier_id = "builtin.web_search"

    def __call__(self, result: Any, *, context: dict[str, Any] | None = None) -> VerificationOutcome:
        text = ""
        records: list[Any] = []
        if isinstance(result, dict):
            text = str(result.get("text") or result.get("content") or result.get("results") or "")
            records = result.get("results") or []
        elif isinstance(result, str):
            text = result
        valid_records = isinstance(records, list) and any(isinstance(r, dict) and r for r in records)
        if not valid_records and len(text.strip()) < 20:
            return VerificationOutcome(
                status=VerificationStatus.FAIL,
                verifier_id=self.verifier_id,
                message="Web search returned insufficient content",
                repair_hint="retry_with_broader_params",
            )
        return VerificationOutcome(
            status=VerificationStatus.PASS,
            verifier_id=self.verifier_id,
            message=f"Web search returned content ({len(text)} chars)",
        )


class _CustomPredicateVerifier:
    def __init__(
        self,
        verifier_id: str,
        predicate: Callable[[Any], bool],
        failure_message: str = "Custom predicate failed",
        repair_hint: str | None = None,
    ) -> None:
        self.verifier_id = verifier_id
        self._predicate = predicate
        self._failure_message = failure_message
        self._repair_hint = repair_hint

    def __call__(self, result: Any, *, context: dict[str, Any] | None = None) -> VerificationOutcome:
        try:
            ok = self._predicate(result)
        except Exception as exc:
            return VerificationOutcome(
                status=VerificationStatus.FAIL,
                verifier_id=self.verifier_id,
                message=f"Predicate raised exception: {exc}",
                repair_hint=self._repair_hint,
            )
        if not ok:
            return VerificationOutcome(
                status=VerificationStatus.FAIL,
                verifier_id=self.verifier_id,
                message=self._failure_message,
                repair_hint=self._repair_hint,
            )
        return VerificationOutcome(
            status=VerificationStatus.PASS,
            verifier_id=self.verifier_id,
            message="Custom predicate passed",
        )


class _CodeTestVerifier:
    verifier_id = "builtin.code_test"

    def __call__(self, result: Any, *, context: dict[str, Any] | None = None) -> VerificationOutcome:
        if isinstance(result, dict):
            passed = result.get("passed", 0)
            failed = result.get("failed", 0)
            exit_code = result.get("exit_code", result.get("returncode", 0))
            if failed > 0 or exit_code != 0:
                summary = str(result.get("raw_summary") or result.get("stderr") or result.get("message") or f"{failed} tests failed")
                return VerificationOutcome(
                    status=VerificationStatus.FAIL,
                    verifier_id=self.verifier_id,
                    message=f"Code test execution failed: {summary[:200]}",
                    repair_hint="retry_step",
                    metadata={"failed": failed, "passed": passed, "exit_code": exit_code},
                )
            return VerificationOutcome(
                status=VerificationStatus.PASS,
                verifier_id=self.verifier_id,
                message=f"Code test execution passed ({passed} tests)",
            )
        return VerificationOutcome(
            status=VerificationStatus.PASS,
            verifier_id=self.verifier_id,
            message="Code test verified",
        )


class _SyntaxVerifier:
    verifier_id = "builtin.syntax"

    def __call__(self, result: Any, *, context: dict[str, Any] | None = None) -> VerificationOutcome:
        if isinstance(result, dict) and result.get("syntax_valid") is False:
            err = str(result.get("error") or "Syntax check failed")
            return VerificationOutcome(
                status=VerificationStatus.FAIL,
                verifier_id=self.verifier_id,
                message=f"Syntax error: {err[:200]}",
                repair_hint="retry_step",
            )
        return VerificationOutcome(
            status=VerificationStatus.PASS,
            verifier_id=self.verifier_id,
            message="Syntax verified valid",
        )


# Singleton instances for common verifiers
NON_EMPTY = _NonEmptyVerifier()
COMMAND_SUCCESS = _CommandSuccessVerifier()
ARTIFACT_PRESENCE = _ArtifactPresenceVerifier()
IMAGE_RESULT = _ImageResultVerifier()
WEB_SEARCH = _WebSearchVerifier()
CODE_TEST = _CodeTestVerifier()
SYNTAX_VALID = _SyntaxVerifier()


# ---------------------------------------------------------------------------
# VerifierRegistry
# ---------------------------------------------------------------------------

class VerifierRegistry:
    """Maps skill_id patterns (glob) to ordered verifier chains.

    When ``run_chain`` is called the registry looks up all patterns that match
    the given ``skill_id`` and concatenates their verifier lists in registration
    order.  A ``QUARANTINE`` outcome short-circuits execution immediately.
    Otherwise every verifier in the chain is called and the worst outcome wins.
    """

    def __init__(self) -> None:
        # Each entry: (glob_pattern, [verifier, ...])
        self._chains: list[tuple[str, list[Verifier]]] = []

        # Register built-in defaults
        self._register_defaults()

    def _register_defaults(self) -> None:
        # Universal: every skill always runs non-empty check
        self.register("*", [NON_EMPTY])
        # Skill-specific
        self.register("image_search", [IMAGE_RESULT])
        self.register("image_generate", [IMAGE_RESULT])
        self.register("web_search", [WEB_SEARCH])
        self.register("web_research", [WEB_SEARCH])
        self.register("web_answer", [WEB_SEARCH])
        self.register("run_command", [COMMAND_SUCCESS])
        self.register("shell_*", [COMMAND_SUCCESS])
        self.register("pdf_generate", [_RequiredKeysVerifier(["status", "downloadUrl"])])
        self.register("artifact_*", [ARTIFACT_PRESENCE])
        self.register("code_test", [CODE_TEST])
        self.register("code_patch", [SYNTAX_VALID])
        self.register("coding_*", [CODE_TEST])

    def register(self, skill_pattern: str, verifiers: list[Verifier]) -> None:
        """Add a verifier chain for skills matching ``skill_pattern`` (glob)."""
        self._chains.append((skill_pattern, list(verifiers)))

    def register_custom(
        self,
        skill_pattern: str,
        verifier_id: str,
        predicate: Callable[[Any], bool],
        *,
        failure_message: str = "Custom predicate failed",
        repair_hint: str | None = None,
    ) -> None:
        """Convenience wrapper to add a custom predicate verifier."""
        v = _CustomPredicateVerifier(
            verifier_id=verifier_id,
            predicate=predicate,
            failure_message=failure_message,
            repair_hint=repair_hint,
        )
        self.register(skill_pattern, [v])

    def _get_chain(self, skill_id: str) -> list[Verifier]:
        chain: list[Verifier] = []
        for pattern, verifiers in self._chains:
            if fnmatch.fnmatch(skill_id, pattern):
                chain.extend(verifiers)
        return chain

    def run_chain(
        self,
        skill_id: str,
        result: Any,
        *,
        context: dict[str, Any] | None = None,
    ) -> list[VerificationOutcome]:
        """Execute the full verifier chain for ``skill_id``.

        Returns the list of all outcomes.  Callers should inspect the list for
        any fatal outcome and stop further processing on the first quarantine.
        """
        outcomes: list[VerificationOutcome] = []
        chain = self._get_chain(skill_id)
        if not chain:
            logger.debug("No verifiers registered for skill_id=%s, defaulting PASS", skill_id)
            return [VerificationOutcome(
                status=VerificationStatus.PASS,
                verifier_id="registry.default",
                message="No verifier chain configured; assuming pass",
            )]

        for verifier in chain:
            try:
                outcome = verifier(result, context=context)
            except Exception as exc:
                outcome = VerificationOutcome(
                    status=VerificationStatus.FAIL,
                    verifier_id=getattr(verifier, "verifier_id", "unknown"),
                    message=f"Verifier raised unhandled exception: {exc}",
                    repair_hint="retry_step",
                )
            outcomes.append(outcome)
            # Security violation short-circuits immediately
            if outcome.status == VerificationStatus.QUARANTINE:
                logger.warning("QUARANTINE from verifier %s for skill %s", outcome.verifier_id, skill_id)
                break

        return outcomes

    def aggregate(self, outcomes: list[VerificationOutcome]) -> VerificationOutcome:
        """Return the single worst outcome from a list (QUARANTINE > FAIL > WARN > PASS)."""
        priority = {
            VerificationStatus.QUARANTINE: 4,
            VerificationStatus.FAIL: 3,
            VerificationStatus.WARN: 2,
            VerificationStatus.PASS: 1,
        }
        worst = max(outcomes, key=lambda o: priority.get(o.status, 0))
        return worst


# ---------------------------------------------------------------------------
# FailureClassifier
# ---------------------------------------------------------------------------

class FailureCategory(str, Enum):
    """Typed failure reason — RepairController maps these to repair strategies."""
    EMPTY_RESULT = "empty_result"
    MISSING_KEYS = "missing_keys"
    COMMAND_FAILURE = "command_failure"
    NO_ARTIFACT = "no_artifact"
    NO_IMAGE = "no_image"
    INSUFFICIENT_CONTENT = "insufficient_content"
    SECURITY_VIOLATION = "security_violation"
    CUSTOM_PREDICATE = "custom_predicate"
    SYNTAX_ERROR = "syntax_error"
    TEST_ASSERTION = "test_assertion"
    DEPENDENCY_MISSING = "dependency_missing"
    CONCURRENT_EDIT = "concurrent_edit"
    COMMAND_TIMEOUT = "command_timeout"
    GIT_PERMISSION_VIOLATION = "git_permission_violation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifiedFailure:
    category: FailureCategory
    outcome: VerificationOutcome
    skill_id: str
    attempt: int
    repair_hint: str | None = None


_CATEGORY_PATTERNS: list[tuple[str, FailureCategory]] = [
    ("non_empty",             FailureCategory.EMPTY_RESULT),
    ("required_keys",         FailureCategory.MISSING_KEYS),
    ("command_success",       FailureCategory.COMMAND_FAILURE),
    ("artifact_presence",     FailureCategory.NO_ARTIFACT),
    ("image_result",          FailureCategory.NO_IMAGE),
    ("web_search",            FailureCategory.INSUFFICIENT_CONTENT),
    ("injection",             FailureCategory.SECURITY_VIOLATION),
    ("quarantine",            FailureCategory.SECURITY_VIOLATION),
    ("syntax",                FailureCategory.SYNTAX_ERROR),
    ("assert",                FailureCategory.TEST_ASSERTION),
    ("code_test",             FailureCategory.TEST_ASSERTION),
    ("modulenotfound",        FailureCategory.DEPENDENCY_MISSING),
    ("cannot find module",    FailureCategory.DEPENDENCY_MISSING),
    ("concurrent_edit",       FailureCategory.CONCURRENT_EDIT),
    ("base_hash",             FailureCategory.CONCURRENT_EDIT),
    ("timeout",               FailureCategory.COMMAND_TIMEOUT),
    ("permission",            FailureCategory.GIT_PERMISSION_VIOLATION),
]


class FailureClassifier:
    """Classifies a failed VerificationOutcome into a FailureCategory."""

    def classify(
        self,
        outcome: VerificationOutcome,
        skill_id: str,
        attempt: int = 0,
    ) -> ClassifiedFailure:
        if outcome.status == VerificationStatus.QUARANTINE:
            return ClassifiedFailure(
                category=FailureCategory.SECURITY_VIOLATION,
                outcome=outcome,
                skill_id=skill_id,
                attempt=attempt,
                repair_hint="escalate_security",
            )

        vid_lower = outcome.verifier_id.lower()
        msg_lower = outcome.message.lower()

        for pattern, category in _CATEGORY_PATTERNS:
            if pattern in vid_lower or pattern in msg_lower:
                return ClassifiedFailure(
                    category=category,
                    outcome=outcome,
                    skill_id=skill_id,
                    attempt=attempt,
                    repair_hint=outcome.repair_hint,
                )

        if "custom" in vid_lower:
            return ClassifiedFailure(
                category=FailureCategory.CUSTOM_PREDICATE,
                outcome=outcome,
                skill_id=skill_id,
                attempt=attempt,
                repair_hint=outcome.repair_hint,
            )

        return ClassifiedFailure(
            category=FailureCategory.UNKNOWN,
            outcome=outcome,
            skill_id=skill_id,
            attempt=attempt,
            repair_hint=outcome.repair_hint,
        )


# ---------------------------------------------------------------------------
# Module-level singleton registry and classifier
# ---------------------------------------------------------------------------

_DEFAULT_REGISTRY = VerifierRegistry()
_DEFAULT_CLASSIFIER = FailureClassifier()


def get_registry() -> VerifierRegistry:
    """Return the process-level default VerifierRegistry."""
    return _DEFAULT_REGISTRY


def get_classifier() -> FailureClassifier:
    """Return the process-level default FailureClassifier."""
    return _DEFAULT_CLASSIFIER
