"""Phase 13 — Verification Engine + Self-Repair tests.

Tests are entirely deterministic — no LLMs, no network, no file I/O.
Each test covers one specific behavioural contract of the engine.
"""
from __future__ import annotations

import pytest

from hinaa_api.agent.verifier_registry import (
    FailureCategory,
    FailureClassifier,
    VerificationStatus,
    VerifierRegistry,
)
from hinaa_api.agent.repair import (
    LoopDetector,
    RepairAction,
    RepairController,
    _build_broader_params,
)


# ---------------------------------------------------------------------------
# 1. VerifierRegistry — built-in chains
# ---------------------------------------------------------------------------

class TestVerifierRegistry:
    """VerifierRegistry: correct chains are invoked for each skill_id."""

    def setup_method(self):
        self.registry = VerifierRegistry()

    def test_non_empty_pass(self):
        outcomes = self.registry.run_chain("some_custom_skill", {"data": "hello"})
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.PASS

    def test_non_empty_fail_on_none(self):
        outcomes = self.registry.run_chain("some_custom_skill", None)
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.FAIL

    def test_non_empty_fail_on_empty_dict(self):
        outcomes = self.registry.run_chain("some_custom_skill", {})
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.FAIL

    def test_web_search_pass_with_records(self):
        result = {"results": [{"title": "A", "url": "http://x.com"}]}
        outcomes = self.registry.run_chain("web_search", result)
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.PASS

    def test_web_search_fail_empty(self):
        outcomes = self.registry.run_chain("web_search", {"results": [], "text": ""})
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.FAIL

    def test_image_search_pass(self):
        result = {"images": ["url1", "url2"]}
        outcomes = self.registry.run_chain("image_search", result)
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.PASS

    def test_image_generate_queued_job_passes(self):
        result = {"status": "queued", "job_id": "abc123"}
        outcomes = self.registry.run_chain("image_generate", result)
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.PASS

    def test_image_generate_empty_fails(self):
        outcomes = self.registry.run_chain("image_generate", {"status": "ok"})
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.FAIL

    def test_run_command_success(self):
        result = {"exit_code": 0, "stdout": "ok"}
        outcomes = self.registry.run_chain("run_command", result)
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.PASS

    def test_run_command_fail_nonzero(self):
        result = {"exit_code": 1, "stderr": "error"}
        outcomes = self.registry.run_chain("run_command", result)
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.FAIL

    def test_shell_glob_matches(self):
        result = {"exit_code": 127, "stderr": "not found"}
        outcomes = self.registry.run_chain("shell_exec", result)
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.FAIL

    def test_artifact_skill_glob(self):
        result = {"artifacts": []}  # no artifact = fail
        outcomes = self.registry.run_chain("artifact_render", result)
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.FAIL

    def test_custom_predicate_verifier(self):
        self.registry.register_custom(
            "my_tool",
            verifier_id="test.custom",
            predicate=lambda r: isinstance(r, dict) and r.get("score", 0) > 0.5,
            failure_message="Score too low",
        )
        outcomes_pass = self.registry.run_chain("my_tool", {"score": 0.9})
        assert self.registry.aggregate(outcomes_pass).status == VerificationStatus.PASS

        outcomes_fail = self.registry.run_chain("my_tool", {"score": 0.1})
        assert self.registry.aggregate(outcomes_fail).status == VerificationStatus.FAIL

    def test_unknown_skill_defaults_to_non_empty(self):
        outcomes = self.registry.run_chain("xyzzy_unknown_skill", "some content")
        assert self.registry.aggregate(outcomes).status == VerificationStatus.PASS

    def test_aggregate_returns_worst(self):
        from hinaa_api.agent.verifier_registry import VerificationOutcome
        outcomes = [
            VerificationOutcome(status=VerificationStatus.PASS,  verifier_id="a", message="ok"),
            VerificationOutcome(status=VerificationStatus.WARN,  verifier_id="b", message="warn"),
            VerificationOutcome(status=VerificationStatus.FAIL,  verifier_id="c", message="fail"),
        ]
        agg = self.registry.aggregate(outcomes)
        assert agg.status == VerificationStatus.FAIL
        assert agg.verifier_id == "c"


# ---------------------------------------------------------------------------
# 2. FailureClassifier — correct category mapping
# ---------------------------------------------------------------------------

class TestFailureClassifier:
    """FailureClassifier maps verifier outcomes to FailureCategory correctly."""

    def setup_method(self):
        self.clf = FailureClassifier()
        from hinaa_api.agent.verifier_registry import VerificationOutcome
        self.make = lambda vid, msg, hint=None: VerificationOutcome(
            status=VerificationStatus.FAIL,
            verifier_id=vid,
            message=msg,
            repair_hint=hint,
        )

    def test_non_empty_maps_to_empty_result(self):
        out = self.make("builtin.non_empty", "Result is None")
        cf = self.clf.classify(out, "some_skill", attempt=0)
        assert cf.category == FailureCategory.EMPTY_RESULT

    def test_required_keys_maps_correctly(self):
        out = self.make("builtin.required_keys", "Missing required keys: ['url']")
        cf = self.clf.classify(out, "pdf_generate", attempt=0)
        assert cf.category == FailureCategory.MISSING_KEYS

    def test_command_failure_maps_correctly(self):
        out = self.make("builtin.command_success", "Command exited with code 1")
        cf = self.clf.classify(out, "run_command", attempt=0)
        assert cf.category == FailureCategory.COMMAND_FAILURE

    def test_image_result_maps_correctly(self):
        out = self.make("builtin.image_result", "No image URL or results returned")
        cf = self.clf.classify(out, "image_search", attempt=1)
        assert cf.category == FailureCategory.NO_IMAGE
        assert cf.attempt == 1

    def test_web_search_maps_to_insufficient_content(self):
        out = self.make("builtin.web_search", "Web search returned insufficient content")
        cf = self.clf.classify(out, "web_search", attempt=0)
        assert cf.category == FailureCategory.INSUFFICIENT_CONTENT

    def test_quarantine_maps_to_security_violation(self):
        from hinaa_api.agent.verifier_registry import VerificationOutcome
        out = VerificationOutcome(
            status=VerificationStatus.QUARANTINE,
            verifier_id="security.injection",
            message="Prompt injection detected",
        )
        cf = self.clf.classify(out, "web_search", attempt=0)
        assert cf.category == FailureCategory.SECURITY_VIOLATION
        assert cf.repair_hint == "escalate_security"

    def test_unknown_falls_through(self):
        out = self.make("some.weird.verifier", "Something exploded", hint="retry_step")
        cf = self.clf.classify(out, "mystery_skill", attempt=0)
        assert cf.category == FailureCategory.UNKNOWN
        assert cf.repair_hint == "retry_step"


# ---------------------------------------------------------------------------
# 3. RepairController — strategy table + loop detector
# ---------------------------------------------------------------------------

class TestRepairController:
    """RepairController selects correct actions per category and attempt."""

    def _make_failure(self, category: FailureCategory, attempt: int, hint: str | None = None):
        from hinaa_api.agent.verifier_registry import VerificationOutcome
        out = VerificationOutcome(
            status=VerificationStatus.FAIL,
            verifier_id="test.verifier",
            message="test failure",
            repair_hint=hint,
        )
        return __import__(
            "hinaa_api.agent.verifier_registry", fromlist=["ClassifiedFailure"]
        ).ClassifiedFailure(
            category=category,
            outcome=out,
            skill_id="test_skill",
            attempt=attempt,
            repair_hint=hint,
        )

    def test_empty_result_attempt0_retries(self):
        ctrl = RepairController()
        f = self._make_failure(FailureCategory.EMPTY_RESULT, 0)
        d = ctrl.decide(f, "step_1")
        assert d.action == RepairAction.RETRY_STEP

    def test_empty_result_attempt1_broadens(self):
        ctrl = RepairController()
        f = self._make_failure(FailureCategory.EMPTY_RESULT, 1)
        d = ctrl.decide(f, "step_1")
        assert d.action == RepairAction.RETRY_BROADER

    def test_empty_result_attempt2_replans(self):
        ctrl = RepairController()
        f = self._make_failure(FailureCategory.EMPTY_RESULT, 2)
        d = ctrl.decide(f, "step_1")
        assert d.action == RepairAction.REPLAN

    def test_security_violation_always_escalates(self):
        ctrl = RepairController()
        f = self._make_failure(FailureCategory.SECURITY_VIOLATION, 0)
        d = ctrl.decide(f, "step_x")
        assert d.action == RepairAction.ESCALATE_SECURITY

    def test_replan_budget_exhausted_aborts(self):
        ctrl = RepairController(max_replans=1)
        f = self._make_failure(FailureCategory.EMPTY_RESULT, 2)
        ctrl.decide(f, "step_1")  # first replan OK
        f2 = self._make_failure(FailureCategory.EMPTY_RESULT, 2)
        d = ctrl.decide(f2, "step_2")  # budget exhausted
        assert d.action == RepairAction.ABORT

    def test_loop_detector_triggers_abort(self):
        # is_looping checks BEFORE recording the new entry.
        # With threshold=3, we need 3 prior entries so the 4th call fires.
        ctrl = RepairController(loop_detector=LoopDetector(window=8, threshold=3))
        f = self._make_failure(FailureCategory.COMMAND_FAILURE, 0, hint="retry_step")
        ctrl.decide(f, "step_loop")  # records entry 1
        ctrl.decide(f, "step_loop")  # records entry 2
        ctrl.decide(f, "step_loop")  # records entry 3
        d = ctrl.decide(f, "step_loop")  # is_looping sees 3 → abort
        assert d.action == RepairAction.ABORT
        assert d.loop_detected is True

    def test_insufficient_content_broadens_params(self):
        ctrl = RepairController()
        f = self._make_failure(FailureCategory.INSUFFICIENT_CONTENT, 0)
        params = {"query": "quantum physics", "num_results": 5}
        d = ctrl.decide(f, "step_ws", current_params=params)
        assert d.action == RepairAction.RETRY_BROADER
        assert d.patch_params.get("num_results", 5) > 5

    def test_no_image_attempt0_broadens(self):
        ctrl = RepairController()
        f = self._make_failure(FailureCategory.NO_IMAGE, 0)
        params = {"query": "sunset -site:pinterest.com", "num_results": 5}
        d = ctrl.decide(f, "step_img", current_params=params)
        assert d.action == RepairAction.RETRY_BROADER
        # Restrictors should be stripped
        assert "-site:" not in d.patch_params.get("query", "")


# ---------------------------------------------------------------------------
# 4. LoopDetector — sliding window
# ---------------------------------------------------------------------------

class TestLoopDetector:
    """LoopDetector correctly identifies cycles within window."""

    def test_no_loop_below_threshold(self):
        ld = LoopDetector(window=8, threshold=3)
        ld.record("s1", "retry_step")
        ld.record("s1", "retry_step")
        assert not ld.is_looping("s1", "retry_step")  # only 2 occurrences

    def test_loop_at_threshold(self):
        ld = LoopDetector(window=8, threshold=3)
        ld.record("s1", "retry_step")
        ld.record("s1", "retry_step")
        ld.record("s1", "retry_step")
        assert ld.is_looping("s1", "retry_step")

    def test_different_steps_no_loop(self):
        ld = LoopDetector(window=8, threshold=3)
        for i in range(5):
            ld.record(f"step_{i}", "retry_step")
        assert not ld.is_looping("step_0", "retry_step")

    def test_window_eviction(self):
        ld = LoopDetector(window=4, threshold=3)
        # Fill window: s1 x3 then evict by adding 4 more different entries
        ld.record("s1", "retry")
        ld.record("s1", "retry")
        ld.record("s1", "retry")
        # Now evict old entries
        ld.record("s2", "replan")
        ld.record("s2", "replan")
        ld.record("s2", "replan")
        ld.record("s2", "replan")
        # s1 entries should be evicted from window
        assert not ld.is_looping("s1", "retry")

    def test_reset_clears_history(self):
        ld = LoopDetector(window=8, threshold=3)
        for _ in range(5):
            ld.record("s1", "retry_step")
        ld.reset()
        assert not ld.is_looping("s1", "retry_step")


# ---------------------------------------------------------------------------
# 5. Parameter broadening helpers
# ---------------------------------------------------------------------------

class TestBuildBroaderParams:
    """_build_broader_params produces expected param patches."""

    def test_no_image_strips_restrictors(self):
        params = {"query": "cat photo -site:instagram.com", "num_results": 5}
        patch = _build_broader_params(FailureCategory.NO_IMAGE, params)
        assert "-site:" not in patch["query"]
        assert patch["num_results"] == 10

    def test_no_image_prepends_photo_of_if_no_restrictors(self):
        params = {"query": "mountain lake", "num_results": 5}
        patch = _build_broader_params(FailureCategory.NO_IMAGE, params)
        assert "photo of" in patch["query"].lower()

    def test_insufficient_content_doubles_results(self):
        params = {"query": "AI news", "num_results": 5}
        patch = _build_broader_params(FailureCategory.INSUFFICIENT_CONTENT, params)
        assert patch["num_results"] == 10
        assert patch.get("search_depth") == "advanced"

    def test_empty_result_doubles_limit(self):
        params = {"limit": 10}
        patch = _build_broader_params(FailureCategory.EMPTY_RESULT, params)
        assert patch["limit"] == 20

    def test_respects_max_cap(self):
        params = {"num_results": 80}
        patch = _build_broader_params(FailureCategory.NO_IMAGE, params)
        assert patch["num_results"] <= 20
