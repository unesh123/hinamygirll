"""Phase 13 — Self-Repair Controller + Loop Detector.

RepairController decides what to do when a step fails:
  - retry_step          → same parameters, increment attempt count
  - retry_with_broader_params → tweak parameters and retry
  - replan             → ask planner to replace failing steps
  - escalate_security  → mark task as quarantined, no retry
  - skip               → mark step as skipped and continue
  - abort              → mark run as failed

LoopDetector prevents infinite repair cycles by tracking
the sliding failure window and detecting repeated (step, hint) pairs.
"""
from __future__ import annotations

import logging
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .verifier_registry import (
    ClassifiedFailure,
    FailureCategory,
    VerificationOutcome,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Repair action
# ---------------------------------------------------------------------------

class RepairAction(str, Enum):
    RETRY_STEP = "retry_step"
    RETRY_BROADER = "retry_with_broader_params"
    REPLAN = "replan"
    SKIP = "skip"
    ESCALATE_SECURITY = "escalate_security"
    ABORT = "abort"


@dataclass
class RepairDecision:
    action: RepairAction
    reason: str
    patch_params: dict[str, Any] = field(default_factory=dict)  # for RETRY_BROADER
    replan_guidance: str | None = None                          # for REPLAN
    loop_detected: bool = False


# ---------------------------------------------------------------------------
# Strategy table: FailureCategory × attempt → RepairAction
# ---------------------------------------------------------------------------

# (category, attempt_0_based) → action
_STRATEGY: dict[tuple[FailureCategory, int], RepairAction] = {
    (FailureCategory.EMPTY_RESULT, 0):         RepairAction.RETRY_STEP,
    (FailureCategory.EMPTY_RESULT, 1):         RepairAction.RETRY_BROADER,
    (FailureCategory.EMPTY_RESULT, 2):         RepairAction.REPLAN,

    (FailureCategory.MISSING_KEYS, 0):         RepairAction.RETRY_STEP,
    (FailureCategory.MISSING_KEYS, 1):         RepairAction.REPLAN,

    (FailureCategory.COMMAND_FAILURE, 0):      RepairAction.RETRY_STEP,
    (FailureCategory.COMMAND_FAILURE, 1):      RepairAction.RETRY_STEP,
    (FailureCategory.COMMAND_FAILURE, 2):      RepairAction.REPLAN,

    (FailureCategory.NO_ARTIFACT, 0):          RepairAction.RETRY_STEP,
    (FailureCategory.NO_ARTIFACT, 1):          RepairAction.REPLAN,

    (FailureCategory.NO_IMAGE, 0):             RepairAction.RETRY_BROADER,
    (FailureCategory.NO_IMAGE, 1):             RepairAction.REPLAN,

    (FailureCategory.INSUFFICIENT_CONTENT, 0): RepairAction.RETRY_BROADER,
    (FailureCategory.INSUFFICIENT_CONTENT, 1): RepairAction.RETRY_BROADER,
    (FailureCategory.INSUFFICIENT_CONTENT, 2): RepairAction.REPLAN,

    (FailureCategory.SECURITY_VIOLATION, 0):   RepairAction.ESCALATE_SECURITY,

    (FailureCategory.CUSTOM_PREDICATE, 0):     RepairAction.RETRY_STEP,
    (FailureCategory.CUSTOM_PREDICATE, 1):     RepairAction.REPLAN,

    (FailureCategory.SYNTAX_ERROR, 0):         RepairAction.RETRY_STEP,
    (FailureCategory.SYNTAX_ERROR, 1):         RepairAction.RETRY_STEP,
    (FailureCategory.SYNTAX_ERROR, 2):         RepairAction.REPLAN,

    (FailureCategory.TEST_ASSERTION, 0):       RepairAction.RETRY_STEP,
    (FailureCategory.TEST_ASSERTION, 1):       RepairAction.RETRY_BROADER,
    (FailureCategory.TEST_ASSERTION, 2):       RepairAction.REPLAN,

    (FailureCategory.DEPENDENCY_MISSING, 0):   RepairAction.RETRY_STEP,
    (FailureCategory.DEPENDENCY_MISSING, 1):   RepairAction.REPLAN,

    (FailureCategory.CONCURRENT_EDIT, 0):      RepairAction.RETRY_STEP,
    (FailureCategory.CONCURRENT_EDIT, 1):      RepairAction.REPLAN,

    (FailureCategory.COMMAND_TIMEOUT, 0):      RepairAction.RETRY_STEP,
    (FailureCategory.COMMAND_TIMEOUT, 1):      RepairAction.REPLAN,

    (FailureCategory.GIT_PERMISSION_VIOLATION, 0): RepairAction.ESCALATE_SECURITY,

    (FailureCategory.UNKNOWN, 0):              RepairAction.RETRY_STEP,
    (FailureCategory.UNKNOWN, 1):              RepairAction.REPLAN,
}


def _lookup_action(category: FailureCategory, attempt: int) -> RepairAction:
    """Get the repair action for a given category and attempt number."""
    # Clamp attempt to the highest defined value for this category
    max_attempt = max(
        (a for (c, a) in _STRATEGY if c == category),
        default=0,
    )
    clamped = min(attempt, max_attempt)
    return _STRATEGY.get((category, clamped), RepairAction.ABORT)


# ---------------------------------------------------------------------------
# LoopDetector
# ---------------------------------------------------------------------------

class LoopDetector:
    """Detects repair cycles within a sliding window.

    A loop is defined as: the same (step_id, repair_hint) pair appears
    ``threshold`` or more times in the last ``window`` observations.
    """

    def __init__(self, window: int = 8, threshold: int = 3) -> None:
        self._window = window
        self._threshold = threshold
        self._history: deque[tuple[str, str]] = deque(maxlen=window)

    def record(self, step_id: str, repair_hint: str | None) -> None:
        key = (step_id, repair_hint or "none")
        self._history.append(key)

    def is_looping(self, step_id: str, repair_hint: str | None) -> bool:
        key = (step_id, repair_hint or "none")
        counts = Counter(self._history)
        return counts[key] >= self._threshold

    def reset(self) -> None:
        self._history.clear()

    @property
    def history(self) -> list[tuple[str, str]]:
        return list(self._history)


# ---------------------------------------------------------------------------
# RepairController
# ---------------------------------------------------------------------------

class RepairController:
    """Decides the repair action for a classified failure.

    Usage::

        controller = RepairController(loop_detector=LoopDetector())
        decision = controller.decide(classified_failure, step_id="step_abc")
        if decision.action == RepairAction.RETRY_STEP:
            ...
    """

    def __init__(
        self,
        loop_detector: LoopDetector | None = None,
        max_replans: int = 2,
    ) -> None:
        self._loop = loop_detector or LoopDetector()
        self._replan_count = 0
        self._max_replans = max_replans

    def decide(
        self,
        failure: ClassifiedFailure,
        step_id: str,
        *,
        current_params: dict[str, Any] | None = None,
    ) -> RepairDecision:
        """Return a RepairDecision for the given classified failure."""

        # 1. Security violation — no retry, no replan
        if failure.category == FailureCategory.SECURITY_VIOLATION:
            self._loop.record(step_id, "escalate_security")
            return RepairDecision(
                action=RepairAction.ESCALATE_SECURITY,
                reason="Security violation detected; aborting repair loop",
            )

        # 2. Loop detection
        if self._loop.is_looping(step_id, failure.repair_hint):
            logger.warning("Loop detected for step %s hint=%s — aborting", step_id, failure.repair_hint)
            return RepairDecision(
                action=RepairAction.ABORT,
                reason=f"Repair loop detected for step {step_id!r} ({failure.category})",
                loop_detected=True,
            )

        # 3. Record and pick action
        self._loop.record(step_id, failure.repair_hint)
        action = _lookup_action(failure.category, failure.attempt)

        # 4. Replan budget check
        if action == RepairAction.REPLAN:
            if self._replan_count >= self._max_replans:
                logger.warning(
                    "Replan budget exhausted (%d/%d) for step %s — aborting",
                    self._replan_count, self._max_replans, step_id,
                )
                return RepairDecision(
                    action=RepairAction.ABORT,
                    reason=f"Replan budget exhausted ({self._replan_count}/{self._max_replans})",
                )
            self._replan_count += 1

        # 5. Build params patch for RETRY_BROADER
        patch: dict[str, Any] = {}
        if action == RepairAction.RETRY_BROADER and current_params:
            patch = _build_broader_params(failure.category, current_params)

        return RepairDecision(
            action=action,
            reason=failure.outcome.message,
            patch_params=patch,
            replan_guidance=failure.outcome.repair_hint or _default_guidance(failure.category),
        )

    def reset_replan_count(self) -> None:
        self._replan_count = 0

    @property
    def replan_count(self) -> int:
        return self._replan_count


# ---------------------------------------------------------------------------
# Parameter broadening helpers
# ---------------------------------------------------------------------------

def _build_broader_params(
    category: FailureCategory,
    current_params: dict[str, Any],
) -> dict[str, Any]:
    """Return a patched params dict with broadened search heuristics."""
    patch: dict[str, Any] = {}

    if category == FailureCategory.NO_IMAGE:
        # Broaden image search — try removing restrictive modifiers
        q = str(current_params.get("query", ""))
        restrictors = [" -site:", " filetype:", " before:", " after:"]
        for r in restrictors:
            q = q.split(r)[0]
        if q == current_params.get("query", ""):
            # No restrictors — try prepending "photo of"
            q = f"photo of {q.strip()}" if q else q
        patch["query"] = q
        patch["num_results"] = min(int(current_params.get("num_results", 5)) * 2, 20)

    elif category == FailureCategory.INSUFFICIENT_CONTENT:
        # Broaden web search
        q = str(current_params.get("query", ""))
        patch["query"] = q
        patch["num_results"] = min(int(current_params.get("num_results", 5)) * 2, 20)
        patch["search_depth"] = "advanced"

    elif category == FailureCategory.EMPTY_RESULT:
        # Generic broadening: increase any limit/count parameter
        for key in ("limit", "count", "max_results", "num_results", "page_size"):
            if key in current_params:
                patch[key] = min(int(current_params[key]) * 2, 100)

    return patch


def _default_guidance(category: FailureCategory) -> str:
    _guide = {
        FailureCategory.EMPTY_RESULT:         "Retry with different parameters or select an alternative tool",
        FailureCategory.MISSING_KEYS:         "Retry step; if issue persists, switch to alternative tool that returns required schema",
        FailureCategory.COMMAND_FAILURE:      "Check environment, retry command",
        FailureCategory.NO_ARTIFACT:          "Retry generation step",
        FailureCategory.NO_IMAGE:             "Broaden search query or use alternative image source",
        FailureCategory.INSUFFICIENT_CONTENT: "Broaden search or use alternative knowledge source",
        FailureCategory.SECURITY_VIOLATION:   "Do not retry; escalate to security review",
        FailureCategory.CUSTOM_PREDICATE:     "Retry or investigate custom constraint",
        FailureCategory.UNKNOWN:              "Retry once, then replan",
    }
    return _guide.get(category, "Replan with alternative strategy")


# ---------------------------------------------------------------------------
# Claude-Code Parity Deterministic Payload Mutation Strategies (REPAIRS)
# ---------------------------------------------------------------------------

def _resolve_error_path(err: dict[str, Any]) -> list[Any]:
    path = err.get("path") if err.get("path") is not None else err.get("loc")
    if isinstance(path, str):
        return [int(p) if p.isdigit() else p for p in path.split(".") if p]
    if isinstance(path, (list, tuple)):
        return list(path)
    return []


def _get_in(d: Any, path: list[Any]) -> Any:
    cur = d
    for p in path:
        cur = cur[p]
    return cur


def _set_in(d: Any, path: list[Any], val: Any) -> None:
    cur = d
    for p in path[:-1]:
        cur = cur[p]
    cur[path[-1]] = val


def clamp_min(minimum: float) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
    def mutate(payload: dict[str, Any], err: dict[str, Any]) -> dict[str, Any]:
        target = payload.get("composition_json") if isinstance(payload.get("composition_json"), dict) else payload
        path = _resolve_error_path(err)
        if path:
            try:
                val = _get_in(target, path)
                _set_in(target, path, max(minimum, float(val)))
                return payload
            except (KeyError, IndexError, TypeError, ValueError):
                try:
                    val = _get_in(payload, path)
                    _set_in(payload, path, max(minimum, float(val)))
                    return payload
                except (KeyError, IndexError, TypeError, ValueError):
                    pass
        for scene in target.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            for layer in scene.get("layers", []):
                if not isinstance(layer, dict):
                    continue
                for kf in layer.get("keyframes", []):
                    if isinstance(kf, dict) and isinstance(kf.get("scale"), (int, float)):
                        kf["scale"] = max(minimum, float(kf["scale"]))
        return payload

    return mutate


def rescale_duration(cap: float) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
    def mutate(payload: dict[str, Any], err: dict[str, Any]) -> dict[str, Any]:
        target = payload.get("composition_json") if isinstance(payload.get("composition_json"), dict) else payload
        scenes = target.get("scenes", [])
        if not scenes:
            return payload
        total = sum(float(s.get("duration", 0.0) or 0.0) for s in scenes)
        if total <= cap or total <= 0:
            return payload
        k = cap / total
        for s in scenes:
            s["duration"] = round(float(s["duration"]) * k, 6)
        drift = cap - sum(float(s["duration"]) for s in scenes)
        scenes[-1]["duration"] = round(max(0.0, float(scenes[-1]["duration"]) + drift), 6)
        return payload

    return mutate


def clamp_layer_timing(payload: dict[str, Any], err: dict[str, Any]) -> dict[str, Any]:
    target = payload.get("composition_json") if isinstance(payload.get("composition_json"), dict) else payload
    for scene in target.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        sd = float(scene.get("duration", 0.0) or 0.0)
        if sd <= 0:
            continue
        if isinstance(scene.get("transition_duration"), (int, float)):
            scene["transition_duration"] = round(max(0.05, min(1.0, float(scene["transition_duration"]), sd)), 6)
        for layer in scene.get("layers", []):
            if not isinstance(layer, dict):
                continue
            start = max(0.0, float(layer.get("start", 0.0) or 0.0))
            if start >= sd:
                start = 0.0
            layer["start"] = round(start, 6)
            if "duration" in layer and isinstance(layer["duration"], (int, float)):
                dur = float(layer["duration"])
                if start + dur > sd:
                    layer["duration"] = round(max(0.0, sd - start), 6)
            if "end" in layer and isinstance(layer["end"], (int, float)):
                end = float(layer["end"])
                if end <= start or end > sd:
                    layer["end"] = round(sd, 6)
    return payload


REPAIRS: list[tuple[Callable[[dict[str, Any]], bool], Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]]] = [
    (lambda e: e.get("type") == "greater_than_equal", clamp_min(0.05)),
    (lambda e: "at most 30 seconds" in str(e.get("msg", "")), rescale_duration(30.0)),
    (lambda e: "must fit inside its scene" in str(e.get("msg", "")), clamp_layer_timing),
]
