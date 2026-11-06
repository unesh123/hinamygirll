"""HINAA OS — Phase 16 Full 96-Scenario Acceptance Test Suite (E16-01 to E16-96).

Covers all 12 evaluation and continuous self-improvement groups:
- Group A: Evaluation Hygiene & Holdout Integrity (E16-01 to E16-08)
- Group B: Dataset Stratification & Partition Balancing (E16-09 to E16-16)
- Group C: Evaluation Oracles & Deterministic Checks (E16-17 to E16-24)
- Group D: Citation Groundedness & Anti-Hallucination (E16-25 to E16-32)
- Group E: Blinded Pairwise Judge & Bias Auditing (E16-33 to E16-40)
- Group F: Reflective Speech & Brevity Oracles (E16-41 to E16-48)
- Group G: Failure Diagnosis & Taxonomy Clustering (E16-49 to E16-56)
- Group H: Adaptive Proposal Engine & Layer Separation (E16-57 to E16-64)
- Group I: Matched Experiments & Statistical Gates (E16-65 to E16-72)
- Group J: Canary Deployment & Telemetry Anomaly Detection (E16-73 to E16-80)
- Group K: Atomic Rollback & Configuration State Restoration (E16-81 to E16-88)
- Group L: Memory Quarantine & Governance Gates (E16-89 to E16-96)
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import time
import unittest
from pathlib import Path

# Add apps/api to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hinaa_api.evals.contracts import (
    CandidateChange,
    CandidateStatus,
    DatasetManifest,
    DatasetPartition,
    EvalCase,
    EvalCaseDomain,
    EvalClass,
    FailureCluster,
    ImprovementProposal,
    PromotionDecision,
    PromotionOutcome,
    QualityMetrics,
    RollbackReceipt,
    ScoreResult,
    ScorerType,
)
from hinaa_api.evals.dataset import DatasetManager
from hinaa_api.evals.evaluators import (
    BlindedPairwiseJudge,
    CitationGroundednessEvaluator,
    DeterministicArtifactEvaluator,
    ReflectiveSpeechEvaluator,
    SecurityGateEvaluator,
)
from hinaa_api.evals.promotion import PromotionController
from hinaa_api.evals.proposal import DiagnosticProposalEngine
from hinaa_api.evals.runner import ExperimentRunner, MatchedComparisonResult
from hinaa_api.evals.store import EvalStore
from hinaa_api.security.contracts import DecisionEffect, PolicyContext
from hinaa_api.security.pdp import PolicyDecisionPoint


# ==============================================================================
# GROUP A: Evaluation Hygiene & Holdout Integrity (E16-01 to E16-08)
# ==============================================================================

class TestGroupA_EvaluationHygieneAndHoldoutIntegrity(unittest.TestCase):
    def setUp(self):
        self.mgr = DatasetManager(dataset_name="hinaa-canonical-eval-v1")
        self.cases = self.mgr.generate_canonical_dataset()

    def test_e16_01_manifest_hash_deterministic(self):
        m1 = self.mgr.manifest
        m2 = self.mgr.manifest
        self.assertEqual(m1.dataset_hash, m2.dataset_hash)
        self.assertEqual(len(m1.dataset_hash), 64)

    def test_e16_02_manifest_hash_sensitive_to_change(self):
        m1 = self.mgr.manifest
        # Alter one prompt in a copy
        altered_cases = [copy.deepcopy(c) for c in self.cases]
        altered_cases[0].prompt = altered_cases[0].prompt + " ALTERED"
        altered_mgr = DatasetManager(dataset_name="hinaa-altered-v1", cases=altered_cases)
        m2 = altered_mgr.manifest
        self.assertNotEqual(m1.dataset_hash, m2.dataset_hash)

    def test_e16_03_holdout_access_denied_to_agent(self):
        holdout_cases = [c for c in self.cases if c.partition == DatasetPartition.SEALED_HOLDOUT]
        target_id = holdout_cases[0].case_id
        with self.assertRaises(PermissionError):
            self.mgr.get_case(target_id, caller_role="agent")

    def test_e16_04_holdout_access_denied_to_proposal_engine(self):
        holdout_cases = [c for c in self.cases if c.partition == DatasetPartition.SEALED_HOLDOUT]
        target_id = holdout_cases[0].case_id
        with self.assertRaises(PermissionError):
            self.mgr.get_case(target_id, caller_role="proposal_engine")

    def test_e16_05_holdout_list_denied_to_agent(self):
        with self.assertRaises(PermissionError):
            self.mgr.list_cases(partition=DatasetPartition.SEALED_HOLDOUT, caller_role="agent")

    def test_e16_06_holdout_access_allowed_to_eval_runner(self):
        holdout_cases = [c for c in self.cases if c.partition == DatasetPartition.SEALED_HOLDOUT]
        target_id = holdout_cases[0].case_id
        case = self.mgr.get_case(target_id, caller_role="eval_runner")
        self.assertEqual(case.case_id, target_id)
        self.assertEqual(case.partition, DatasetPartition.SEALED_HOLDOUT)

    def test_e16_07_contamination_detector_catches_leak(self):
        leak_text = "In a synchronous network with f Byzantine faulty nodes what is the minimum total number of nodes N required for consensus"
        leak_check = self.mgr.check_contamination(leak_text)
        self.assertTrue(leak_check.is_contaminated)
        self.assertEqual(leak_check.matched_case_id, "CASE-RSN-027")

    def test_e16_08_contamination_detector_passes_benign(self):
        clean_text = "Deploying an optimized FastAPI microservice in Pokhara using Docker and Kubernetes."
        clean_check = self.mgr.check_contamination(clean_text)
        self.assertFalse(clean_check.is_contaminated)


# ==============================================================================
# GROUP B: Dataset Stratification & Partition Balancing (E16-09 to E16-16)
# ==============================================================================

class TestGroupB_DatasetStratificationAndPartitionBalancing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mgr = DatasetManager(dataset_name="hinaa-canonical-eval-v1")
        cls.cases = cls.mgr.generate_canonical_dataset()

    def test_e16_09_canonical_dataset_240_cases(self):
        self.assertEqual(len(self.cases), 240)
        self.assertEqual(self.mgr.total_count, 240)

    def test_e16_10_eight_domains_30_cases_each(self):
        counts = {}
        for c in self.cases:
            counts[c.domain] = counts.get(c.domain, 0) + 1
        self.assertEqual(len(counts), 8)
        for domain in EvalCaseDomain:
            self.assertEqual(counts[domain], 30)

    def test_e16_11_dev_partition_144_cases(self):
        dev = [c for c in self.cases if c.partition == DatasetPartition.DEV_POOL]
        self.assertEqual(len(dev), 144)
        self.assertEqual(self.mgr.manifest.dev_count, 144)

    def test_e16_12_val_partition_48_cases(self):
        val = [c for c in self.cases if c.partition == DatasetPartition.VAL_POOL]
        self.assertEqual(len(val), 48)
        self.assertEqual(self.mgr.manifest.val_count, 48)

    def test_e16_13_holdout_partition_48_cases(self):
        hold = [c for c in self.cases if c.partition == DatasetPartition.SEALED_HOLDOUT]
        self.assertEqual(len(hold), 48)
        self.assertEqual(self.mgr.manifest.holdout_count, 48)

    def test_e16_14_domain_stratification_balance(self):
        for domain in EvalCaseDomain:
            dom_cases = [c for c in self.cases if c.domain == domain]
            dev = [c for c in dom_cases if c.partition == DatasetPartition.DEV_POOL]
            val = [c for c in dom_cases if c.partition == DatasetPartition.VAL_POOL]
            hold = [c for c in dom_cases if c.partition == DatasetPartition.SEALED_HOLDOUT]
            self.assertEqual(len(dev), 18)
            self.assertEqual(len(val), 6)
            self.assertEqual(len(hold), 6)

    def test_e16_15_all_cases_valid_metadata_and_tags(self):
        for c in self.cases:
            self.assertTrue(c.case_id.startswith("CASE-"))
            self.assertIsInstance(c.domain, EvalCaseDomain)
            self.assertIsInstance(c.partition, DatasetPartition)
            self.assertIsInstance(c.scorer_type, ScorerType)
            self.assertTrue(len(c.tags) > 0)
            self.assertTrue(len(c.prompt) > 0)

    def test_e16_16_deterministic_dataset_generation(self):
        mgr2 = DatasetManager(dataset_name="hinaa-canonical-eval-v1")
        cases2 = mgr2.generate_canonical_dataset()
        self.assertEqual(self.mgr.manifest.dataset_hash, mgr2.manifest.dataset_hash)
        for c1, c2 in zip(self.cases, cases2):
            self.assertEqual(c1.case_id, c2.case_id)
            self.assertEqual(c1.partition, c2.partition)


# ==============================================================================
# GROUP C: Evaluation Oracles & Deterministic Checks (E16-17 to E16-24)
# ==============================================================================

class TestGroupC_EvaluationOraclesAndDeterministicChecks(unittest.TestCase):
    def setUp(self):
        self.evaluator = DeterministicArtifactEvaluator()

    def test_e16_17_deterministic_regex_match_pass(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-1",
            output_text="Transaction TX-99442 completed successfully.",
            expected_outputs={"pattern": r"TX-\d{5}"},
        )
        self.assertTrue(res.passed)
        self.assertEqual(res.score, 1.0)

    def test_e16_18_deterministic_regex_match_fail(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-1",
            output_text="Transaction FAILED without id.",
            expected_outputs={"pattern": r"TX-\d{5}"},
        )
        self.assertFalse(res.passed)
        self.assertEqual(res.score, 0.0)

    def test_e16_19_deterministic_numeric_ground_truth_pass(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-1",
            output_text="The total amount computed is 18856 paisa.",
            expected_outputs={"ground_truth": "18856"},
        )
        self.assertTrue(res.passed)
        self.assertEqual(res.score, 1.0)

    def test_e16_20_deterministic_numeric_ground_truth_fail(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-1",
            output_text="The total amount computed is 12000 paisa.",
            expected_outputs={"ground_truth": "18856"},
        )
        self.assertFalse(res.passed)
        self.assertEqual(res.score, 0.0)

    def test_e16_21_deterministic_quality_metrics_structure(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-1",
            output_text="Output 42",
            expected_outputs={"ground_truth": "42"},
        )
        self.assertIsInstance(res.metrics, QualityMetrics)
        self.assertEqual(res.metrics.correctness, 1.0)

    def test_e16_22_deterministic_confidence_interval(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-1",
            output_text="Output 42",
            expected_outputs={"ground_truth": "42"},
        )
        self.assertEqual(list(res.confidence_interval), [1.0, 1.0])

    def test_e16_23_deterministic_rationale_populated(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-1",
            output_text="Output 42",
            expected_outputs={"ground_truth": "42"},
        )
        self.assertIn("rationale", res.details)
        self.assertTrue(len(res.details["rationale"]) > 0)

    def test_e16_24_deterministic_scorer_type_tag(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-1",
            output_text="Output 42",
            expected_outputs={"ground_truth": "42"},
        )
        self.assertEqual(res.details["scorer_type"], ScorerType.DETERMINISTIC_ARTIFACT.value)


# ==============================================================================
# GROUP D: Citation Groundedness & Anti-Hallucination (E16-25 to E16-32)
# ==============================================================================

class TestGroupD_CitationGroundednessAndAntiHallucination(unittest.TestCase):
    def setUp(self):
        self.evaluator = CitationGroundednessEvaluator()

    def test_e16_25_groundedness_valid_citation_passes(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-d1",
            output_text="According to the latest census [1], Kathmandu has over 1 million residents.",
            expected_outputs={},
            context={"available_sources": ["1", "2"]},
        )
        self.assertTrue(res.passed)
        self.assertEqual(res.score, 1.0)

    def test_e16_26_groundedness_fabricated_citation_fails(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-d2",
            output_text="The quantum flux was discovered in 1910 [999].",
            expected_outputs={},
            context={"available_sources": ["1", "2"]},
        )
        self.assertFalse(res.passed)
        self.assertEqual(res.score, 0.0)
        self.assertIn("999", res.details["fabricated_citations"])

    def test_e16_27_groundedness_named_source_citation(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-d3",
            output_text="Security rules are defined in the master policy [Source-SecDocs].",
            expected_outputs={},
            context={"available_sources": ["Source-SecDocs"]},
        )
        self.assertTrue(res.passed)
        self.assertIn("Source-SecDocs", res.details["valid_citations"])

    def test_e16_28_groundedness_precision_calculation(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-d4",
            output_text="Point A [1] and Point B [999].",
            expected_outputs={},
            context={"available_sources": ["1"]},
        )
        self.assertFalse(res.passed)
        self.assertAlmostEqual(res.details["precision"], 0.5, places=2)

    def test_e16_29_groundedness_recall_calculation(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-d5",
            output_text="Point A [1].",
            expected_outputs={},
            context={"available_sources": ["1", "2"]},
        )
        self.assertTrue(res.passed)
        self.assertAlmostEqual(res.details["recall"], 0.5, places=2)

    def test_e16_30_groundedness_missing_required_citation(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-d6",
            output_text="Claim made with zero citations.",
            expected_outputs={"requires_citation": "true"},
            context={"available_sources": ["1"]},
        )
        self.assertFalse(res.passed)
        self.assertEqual(res.score, 0.0)

    def test_e16_31_groundedness_no_citations_required(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-d7",
            output_text="Simple factual greeting or calculation.",
            expected_outputs={},
            context={},
        )
        self.assertTrue(res.passed)
        self.assertEqual(res.score, 1.0)

    def test_e16_32_groundedness_multiple_citations_mixed(self):
        res = self.evaluator.evaluate(
            run_id="run-1",
            case_id="case-d8",
            output_text="Fact 1 [1] and Fact 2 [2] and Fake Fact [777].",
            expected_outputs={},
            context={"available_sources": ["1", "2"]},
        )
        self.assertFalse(res.passed)
        self.assertEqual(len(res.details["valid_citations"]), 2)
        self.assertEqual(len(res.details["fabricated_citations"]), 1)


# ==============================================================================
# GROUP E: Blinded Pairwise Judge & Bias Auditing (E16-33 to E16-40)
# ==============================================================================

class TestGroupE_BlindedPairwiseJudgeAndBiasAuditing(unittest.TestCase):
    def setUp(self):
        self.judge = BlindedPairwiseJudge()

    def test_e16_33_blinded_judge_ab_and_ba_evaluation(self):
        ans_a = "NPR 18,856 paisa (Rs 188.56) is the exact 13% VAT."
        ans_b = "188.56 rupees VAT."
        winner, calib = self.judge.compare("CASE-1", ans_a, ans_b)
        self.assertIn(winner, ["A", "B", "TIE"])

    def test_e16_34_blinded_judge_position_bias_rate(self):
        ans_a = "Kathmandu is the capital of Nepal."
        ans_b = "The capital of Nepal is Kathmandu."
        _, calib = self.judge.compare("CASE-2", ans_a, ans_b)
        self.assertLess(calib.position_bias_rate, 0.10)

    def test_e16_35_blinded_judge_verbosity_penalty(self):
        concise = "NPR 18,856 paisa (Rs 188.56) is the exact 13% VAT on Rs 1,450.50."
        fluffy = (
            "Well, in order to calculate the tax we first have to take the number 1450.50 and "
            "then we convert it into paisa and then we look at 13 percent and do math and "
            "eventually we reach around 188.56 rupees or so after extensive multiplication steps."
        )
        winner, _ = self.judge.compare("CASE-COM-001", concise, fluffy)
        self.assertEqual(winner, "A")

    def test_e16_36_blinded_judge_agreement_with_humans(self):
        ans_a = "Short precise response."
        ans_b = "Long wordy rambling response without clear answer."
        _, calib = self.judge.compare("CASE-3", ans_a, ans_b)
        self.assertGreaterEqual(calib.agreement_with_humans, 0.90)

    def test_e16_37_blinded_judge_tie_detection(self):
        ans = "Identical text on both sides."
        winner, _ = self.judge.compare("CASE-4", ans, ans)
        self.assertEqual(winner, "TIE")

    def test_e16_38_blinded_judge_false_positive_rate(self):
        _, calib = self.judge.compare("CASE-5", "Alpha", "Beta")
        self.assertLessEqual(calib.false_positive_rate, 0.05)

    def test_e16_39_blinded_judge_false_negative_rate(self):
        _, calib = self.judge.compare("CASE-6", "Alpha", "Beta")
        self.assertLessEqual(calib.false_negative_rate, 0.05)

    def test_e16_40_blinded_judge_calibration_id_generated(self):
        _, calib = self.judge.compare("CASE-7", "Alpha", "Beta")
        self.assertTrue(calib.calibration_id.startswith("cal-"))
        self.assertGreater(calib.calibrated_at, 0)


# ==============================================================================
# GROUP F: Reflective Speech & Brevity Oracles (E16-41 to E16-48)
# ==============================================================================

class TestGroupF_ReflectiveSpeechAndBrevityOracles(unittest.TestCase):
    def setUp(self):
        self.oracle = ReflectiveSpeechEvaluator()

    def test_e16_41_speech_brevity_pass(self):
        spoken = "Certainly. The cluster memory has been synchronized and 42 entries are verified."
        res = self.oracle.evaluate(
            run_id="run-1",
            case_id="case-sp1",
            output_text=spoken,
            expected_outputs={"max_spoken_words": "30"},
        )
        self.assertTrue(res.passed)
        self.assertLessEqual(res.details["word_count"], 30)

    def test_e16_42_speech_brevity_fail(self):
        spoken = " ".join(["word"] * 50)
        res = self.oracle.evaluate(
            run_id="run-1",
            case_id="case-sp2",
            output_text=spoken,
            expected_outputs={"max_spoken_words": "20"},
        )
        self.assertFalse(res.passed)
        self.assertGreater(res.details["word_count"], 20)

    def test_e16_43_speech_fact_recall_pass(self):
        spoken = "The backup completed at Pokhara datacenter with 100 percent integrity."
        res = self.oracle.evaluate(
            run_id="run-1",
            case_id="case-sp3",
            output_text=spoken,
            expected_outputs={"max_spoken_words": "30", "required_facts": ["Pokhara", "integrity"]},
        )
        self.assertTrue(res.passed)
        self.assertEqual(res.metrics.correctness, 1.0)

    def test_e16_44_speech_fact_recall_fail(self):
        spoken = "The backup completed somewhere without incident."
        res = self.oracle.evaluate(
            run_id="run-1",
            case_id="case-sp4",
            output_text=spoken,
            expected_outputs={"max_spoken_words": "30", "required_facts": ["Pokhara", "integrity"]},
        )
        self.assertFalse(res.passed)
        self.assertLess(res.metrics.correctness, 0.8)

    def test_e16_45_speech_ssml_valid(self):
        ssml = '<speak><prosody rate="fast">The server is ready.</prosody></speak>'
        res = self.oracle.evaluate(
            run_id="run-1",
            case_id="case-sp5",
            output_text=ssml,
            expected_outputs={"max_spoken_words": "20"},
        )
        self.assertTrue(res.details["ssml_valid"])
        self.assertTrue(res.passed)

    def test_e16_46_speech_ssml_invalid(self):
        invalid_ssml = '<speak><prosody rate="fast">The server is ready.'
        res = self.oracle.evaluate(
            run_id="run-1",
            case_id="case-sp6",
            output_text=invalid_ssml,
            expected_outputs={"max_spoken_words": "20"},
        )
        self.assertFalse(res.details["ssml_valid"])
        self.assertFalse(res.passed)

    def test_e16_47_speech_score_calculation(self):
        spoken = "All 5 nodes are healthy."
        res = self.oracle.evaluate(
            run_id="run-1",
            case_id="case-sp7",
            output_text=spoken,
            expected_outputs={"max_spoken_words": "10", "required_facts": ["5 nodes"]},
        )
        self.assertGreaterEqual(res.score, 0.9)

    def test_e16_48_speech_rationale_details(self):
        spoken = "Task done."
        res = self.oracle.evaluate(
            run_id="run-1",
            case_id="case-sp8",
            output_text=spoken,
            expected_outputs={"max_spoken_words": "10"},
        )
        self.assertIn("word_count", res.details)
        self.assertIn("max_words", res.details)
        self.assertIn("ssml_valid", res.details)


# ==============================================================================
# GROUP G: Failure Diagnosis & Taxonomy Clustering (E16-49 to E16-56)
# ==============================================================================

class TestGroupG_FailureDiagnosisAndTaxonomyClustering(unittest.TestCase):
    def setUp(self):
        self.engine = DiagnosticProposalEngine()

    def test_e16_49_diagnosis_citation_mismatch(self):
        score = ScoreResult(
            score_id="s1", case_id="c1", run_id="r1", evaluator_name="cit",
            score=0.0, passed=False, metrics=QualityMetrics(),
            details={"rationale": "Fabricated citation [999] was detected."},
            created_at=time.time(),
        )
        clusters = self.engine.diagnose_failures([score])
        self.assertIn(FailureCluster.CITATION_MISMATCH, clusters)

    def test_e16_50_diagnosis_excessive_verbosity(self):
        score = ScoreResult(
            score_id="s2", case_id="c2", run_id="r1", evaluator_name="speech",
            score=0.0, passed=False, metrics=QualityMetrics(),
            details={"rationale": "Spoken words 72 exceeded max allowed 45 words/brevity."},
            created_at=time.time(),
        )
        clusters = self.engine.diagnose_failures([score])
        self.assertIn(FailureCluster.EXCESSIVE_VERBOSITY, clusters)

    def test_e16_51_diagnosis_nepali_mistranslation(self):
        score = ScoreResult(
            score_id="s3", case_id="c3", run_id="r1", evaluator_name="det",
            score=0.0, passed=False, metrics=QualityMetrics(),
            details={"rationale": "Devanagari respectful translation missing honorific in Nepali."},
            created_at=time.time(),
        )
        clusters = self.engine.diagnose_failures([score])
        self.assertIn(FailureCluster.NEPALI_MISTRANSLATION, clusters)

    def test_e16_52_diagnosis_permission_failure(self):
        score = ScoreResult(
            score_id="s4", case_id="c4", run_id="r1", evaluator_name="sec",
            score=0.0, passed=False, metrics=QualityMetrics(),
            details={"rationale": "CRITICAL: Security PDP violation permitted without permission."},
            created_at=time.time(),
        )
        clusters = self.engine.diagnose_failures([score])
        self.assertIn(FailureCluster.PERMISSION_FAILURE, clusters)

    def test_e16_53_diagnosis_timeout(self):
        score = ScoreResult(
            score_id="s5", case_id="c5", run_id="r1", evaluator_name="runner",
            score=0.0, passed=False, metrics=QualityMetrics(),
            details={"rationale": "Operation timed out after 30000ms."},
            created_at=time.time(),
        )
        clusters = self.engine.diagnose_failures([score])
        self.assertIn(FailureCluster.TIMEOUT, clusters)

    def test_e16_54_diagnosis_wrong_tool(self):
        score = ScoreResult(
            score_id="s6", case_id="c6", run_id="r1", evaluator_name="runner",
            score=0.0, passed=False, metrics=QualityMetrics(),
            details={"rationale": "Selected wrong tool for arithmetic operation."},
            created_at=time.time(),
        )
        clusters = self.engine.diagnose_failures([score])
        self.assertIn(FailureCluster.WRONG_TOOL, clusters)

    def test_e16_55_diagnosis_stale_memory(self):
        score = ScoreResult(
            score_id="s7", case_id="c7", run_id="r1", evaluator_name="runner",
            score=0.0, passed=False, metrics=QualityMetrics(),
            details={"rationale": "Used stale memory entity from expired session."},
            created_at=time.time(),
        )
        clusters = self.engine.diagnose_failures([score])
        self.assertIn(FailureCluster.STALE_MEMORY, clusters)

    def test_e16_56_diagnosis_ignores_passed_cases(self):
        passed_score = ScoreResult(
            score_id="s8", case_id="c8", run_id="r1", evaluator_name="det",
            score=1.0, passed=True, metrics=QualityMetrics(),
            details={"rationale": "All checks passed."},
            created_at=time.time(),
        )
        clusters = self.engine.diagnose_failures([passed_score])
        self.assertEqual(len(clusters), 0)


# ==============================================================================
# GROUP H: Adaptive Proposal Engine & Layer Separation (E16-57 to E16-64)
# ==============================================================================

class TestGroupH_AdaptiveProposalEngineAndLayerSeparation(unittest.TestCase):
    def setUp(self):
        self.engine = DiagnosticProposalEngine()
        self.clusters = {
            FailureCluster.CITATION_MISMATCH: [
                ScoreResult(score_id="s1", case_id="c1", run_id="r1", evaluator_name="cit", score=0.0, passed=False, metrics=QualityMetrics(), details={"rationale": "cit"}, created_at=time.time())
            ],
            FailureCluster.EXCESSIVE_VERBOSITY: [
                ScoreResult(score_id="s2", case_id="c2", run_id="r1", evaluator_name="sp", score=0.0, passed=False, metrics=QualityMetrics(), details={"rationale": "verb"}, created_at=time.time())
            ],
        }
        self.proposals = self.engine.generate_proposals("snap-test-h", self.clusters)

    def test_e16_57_proposals_weights_updated_strictly_false(self):
        for _, cand in self.proposals:
            self.assertFalse(cand.weights_updated)

    def test_e16_58_proposals_status_proposed(self):
        for _, cand in self.proposals:
            self.assertEqual(cand.status, CandidateStatus.PROPOSED)

    def test_e16_59_proposals_blast_radius_bounded(self):
        for prop, _ in self.proposals:
            self.assertLessEqual(float(prop.blast_radius), 0.10)

    def test_e16_60_proposals_target_layer_assigned(self):
        for _, cand in self.proposals:
            self.assertIn(cand.target_layer, ["prompt", "prompts", "retrieval", "speech_template", "routing"])

    def test_e16_61_proposals_diff_generated(self):
        for _, cand in self.proposals:
            self.assertTrue(len(cand.patch_diff) > 0)

    def test_e16_62_proposals_hashes_populated(self):
        for _, cand in self.proposals:
            self.assertTrue(len(cand.config_hash_before) > 0)
            self.assertTrue(len(cand.config_hash_after) > 0)
            self.assertNotEqual(cand.config_hash_before, cand.config_hash_after)

    def test_e16_63_proposals_forbidden_paths_guarded(self):
        self.assertIn("apps/api/hinaa_api/security/pdp.py", self.engine.FORBIDDEN_MUTATION_PATHS)
        self.assertIn("apps/api/hinaa_api/billing/", self.engine.FORBIDDEN_MUTATION_PATHS)

    def test_e16_64_proposals_iteration_limit(self):
        engine_limited = DiagnosticProposalEngine(max_iterations=1)
        proposals_limited = engine_limited.generate_proposals("snap-1", self.clusters)
        self.assertLessEqual(len(proposals_limited), 1)


# ==============================================================================
# GROUP I: Matched Experiments & Statistical Gates (E16-65 to E16-72)
# ==============================================================================

class TestGroupI_MatchedExperimentsAndStatisticalGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = EvalStore(db_path=":memory:")
        cls.dataset_mgr = DatasetManager(dataset_name="hinaa-canonical-eval-v1")
        cls.runner = ExperimentRunner(store=cls.store, dataset_manager=cls.dataset_mgr)
        cls.candidate = CandidateChange(
            candidate_id="cand-test-i",
            proposal_id="prop-i",
            target_layer="prompts",
            description="Brevity enforcement patch",
            patch_diff="max_spoken_words: 35",
            config_hash_before="hash_b_111",
            config_hash_after="hash_a_222",
            weights_updated=False,
            status=CandidateStatus.PROPOSED,
            created_at=time.time(),
        )
        cls.result = cls.runner.run_matched_experiment(cls.candidate, partition=DatasetPartition.VAL_POOL)

    def test_e16_65_matched_experiment_runs(self):
        self.assertIsInstance(self.result, MatchedComparisonResult)
        self.assertEqual(self.result.candidate_id, "cand-test-i")

    def test_e16_66_matched_baseline_pass_rate(self):
        self.assertGreater(self.result.baseline_pass_rate, 0.0)
        self.assertLessEqual(self.result.baseline_pass_rate, 1.0)

    def test_e16_67_matched_candidate_pass_rate(self):
        self.assertGreater(self.result.candidate_pass_rate, 0.0)
        self.assertLessEqual(self.result.candidate_pass_rate, 1.0)

    def test_e16_68_matched_pass_rate_delta(self):
        expected_delta = round(self.result.candidate_pass_rate - self.result.baseline_pass_rate, 3)
        self.assertEqual(self.result.pass_rate_delta, expected_delta)

    def test_e16_69_matched_p50_latency(self):
        self.assertGreater(self.result.baseline_latency_p50, 0.0)
        self.assertGreater(self.result.candidate_latency_p50, 0.0)

    def test_e16_70_matched_p95_latency(self):
        cand_run = self.store.get_run(self.result.candidate_run_id)
        self.assertGreater(cand_run.p95_latency_ms, 0.0)
        self.assertGreater(self.result.candidate_latency_p50, 0.0)

    def test_e16_71_matched_cost_paisa_integer(self):
        self.assertIsInstance(self.result.baseline_cost_paisa, int)
        self.assertIsInstance(self.result.candidate_cost_paisa, int)
        self.assertGreater(self.result.candidate_cost_paisa, 0)

    def test_e16_72_matched_regression_flag(self):
        self.assertEqual(self.result.is_regression, self.result.pass_rate_delta < 0.0)


# ==============================================================================
# GROUP J: Canary Deployment & Telemetry Anomaly Detection (E16-73 to E16-80)
# ==============================================================================

class TestGroupJ_CanaryDeploymentAndTelemetryAnomalyDetection(unittest.TestCase):
    def setUp(self):
        self.store = EvalStore(db_path=":memory:")
        self.ctrl = PromotionController(store=self.store)
        self.cand = CandidateChange(
            candidate_id="cand-j-test",
            proposal_id="prop-j",
            target_layer="prompts",
            description="System prompt enhancement",
            patch_diff="strict: true",
            config_hash_before="pre_hash_123",
            config_hash_after="post_hash_456",
            weights_updated=False,
            status=CandidateStatus.PROPOSED,
            created_at=time.time(),
        )
        self.store.save_candidate(self.cand)

    def test_e16_73_canary_stage_normal(self):
        res = self.ctrl.execute_canary_stage(self.cand, traffic_pct=10, simulated_error_rate=0.0)
        self.assertEqual(res["canary_status"], "HEALTHY")

    def test_e16_74_canary_ready_for_promotion(self):
        res = self.ctrl.execute_canary_stage(self.cand, traffic_pct=10, simulated_error_rate=0.01)
        self.assertTrue(res["ready_for_full_promotion"])

    def test_e16_75_canary_anomaly_triggers_abort(self):
        res = self.ctrl.execute_canary_stage(self.cand, traffic_pct=10, simulated_error_rate=0.03)
        self.assertEqual(res["canary_status"], "ABORTED_ROLLED_BACK")

    def test_e16_76_canary_abort_updates_candidate_status(self):
        self.ctrl.execute_canary_stage(self.cand, traffic_pct=10, simulated_error_rate=0.05)
        updated = self.store.get_candidate(self.cand.candidate_id)
        self.assertEqual(updated.status, CandidateStatus.ROLLED_BACK)

    def test_e16_77_canary_abort_provides_rollback_receipt(self):
        res = self.ctrl.execute_canary_stage(self.cand, traffic_pct=10, simulated_error_rate=0.05)
        receipt = res["rollback_receipt"]
        self.assertEqual(receipt["candidate_id"], self.cand.candidate_id)
        self.assertEqual(receipt["restored_config_hash"], "pre_hash_123")

    def test_e16_78_canary_traffic_percentage_tracked(self):
        res = self.ctrl.execute_canary_stage(self.cand, traffic_pct=25, simulated_error_rate=0.0)
        self.assertEqual(res["traffic_pct"], 25)

    def test_e16_79_canary_threshold_boundary(self):
        res = self.ctrl.execute_canary_stage(self.cand, traffic_pct=10, simulated_error_rate=0.02)
        self.assertEqual(res["canary_status"], "HEALTHY")

    def test_e16_80_canary_error_rate_reported(self):
        res = self.ctrl.execute_canary_stage(self.cand, traffic_pct=10, simulated_error_rate=0.015)
        self.assertEqual(res["error_rate"], 0.015)


# ==============================================================================
# GROUP K: Atomic Rollback & Configuration State Restoration (E16-81 to E16-88)
# ==============================================================================

class TestGroupK_AtomicRollbackAndConfigurationStateRestoration(unittest.TestCase):
    def setUp(self):
        self.store = EvalStore(db_path=":memory:")
        self.ctrl = PromotionController(store=self.store)
        self.cand = CandidateChange(
            candidate_id="cand-k-test",
            proposal_id="prop-k",
            target_layer="retrieval",
            description="Experimental chunk size",
            patch_diff="chunk: 8",
            config_hash_before="hash_golden_baseline_k",
            config_hash_after="hash_broken_candidate_k",
            weights_updated=False,
            status=CandidateStatus.PROPOSED,
            created_at=time.time(),
        )
        self.store.save_candidate(self.cand)

    def test_e16_81_rollback_execution_success(self):
        receipt = self.ctrl.execute_rollback(self.cand.candidate_id, reason="Performance degradation")
        self.assertIsInstance(receipt, RollbackReceipt)

    def test_e16_82_rollback_restores_config_hash_before(self):
        receipt = self.ctrl.execute_rollback(self.cand.candidate_id, reason="Degradation")
        self.assertEqual(receipt.restored_config_hash, "hash_golden_baseline_k")

    def test_e16_83_rollback_candidate_status_transition(self):
        self.ctrl.execute_rollback(self.cand.candidate_id, reason="Degradation")
        updated = self.store.get_candidate(self.cand.candidate_id)
        self.assertEqual(updated.status, CandidateStatus.ROLLED_BACK)

    def test_e16_84_rollback_recorded_in_store(self):
        receipt = self.ctrl.execute_rollback(self.cand.candidate_id, reason="Audit test")
        self.assertTrue(receipt.rollback_id.startswith("rbk-"))

    def test_e16_85_rollback_trigger_reason_preserved(self):
        receipt = self.ctrl.execute_rollback(self.cand.candidate_id, reason="Latency spike p95 > 250ms")
        self.assertEqual(receipt.trigger_reason, "Latency spike p95 > 250ms")

    def test_e16_86_rollback_restored_by_attribution(self):
        receipt = self.ctrl.execute_rollback(self.cand.candidate_id, reason="Manual intervention", restored_by="dev_lead")
        self.assertEqual(receipt.restored_by, "dev_lead")

    def test_e16_87_rollback_missing_candidate_raises(self):
        with self.assertRaises(KeyError):
            self.ctrl.execute_rollback("non-existent-candidate-id", reason="Test")

    def test_e16_88_rollback_execution_speed(self):
        t0 = time.time()
        self.ctrl.execute_rollback(self.cand.candidate_id, reason="Speed test")
        duration_ms = (time.time() - t0) * 1000
        self.assertLess(duration_ms, 100.0)


# ==============================================================================
# GROUP L: Memory Quarantine & Governance Gates (E16-89 to E16-96)
# ==============================================================================

class TestGroupL_MemoryQuarantineAndGovernanceGates(unittest.TestCase):
    def setUp(self):
        self.store = EvalStore(db_path=":memory:")
        self.dataset_mgr = DatasetManager(dataset_name="hinaa-canonical-eval-v1")
        self.ctrl = PromotionController(store=self.store)
        self.runner = ExperimentRunner(store=self.store, dataset_manager=self.dataset_mgr)
        self.cand = CandidateChange(
            candidate_id="cand-l-test",
            proposal_id="prop-l",
            target_layer="prompts",
            description="Brevity enforcement",
            patch_diff="max_words: 35",
            config_hash_before="hash_before_l",
            config_hash_after="hash_after_l",
            weights_updated=False,
            status=CandidateStatus.PROPOSED,
            created_at=time.time(),
        )
        self.store.save_candidate(self.cand)
        self.comparison = self.runner.run_matched_experiment(self.cand, partition=DatasetPartition.VAL_POOL)

    def test_e16_89_promotion_security_clean_required(self):
        decision = self.ctrl.evaluate_promotion_eligibility(
            self.cand, self.comparison, security_clean=False
        )
        self.assertEqual(decision.outcome, PromotionOutcome.REJECTED_SECURITY_VETO)
        self.assertFalse(decision.security_gate_passed)

    def test_e16_90_promotion_regression_rejected(self):
        regressed_comp = copy.deepcopy(self.comparison)
        regressed_comp.pass_rate_delta = -0.15
        regressed_comp.is_regression = True
        decision = self.ctrl.evaluate_promotion_eligibility(self.cand, regressed_comp, security_clean=True)
        self.assertEqual(decision.outcome, PromotionOutcome.REJECTED_GATE_FAILURE)

    def test_e16_91_promotion_tier_c_token_required(self):
        sec_cand = copy.deepcopy(self.cand)
        sec_cand.target_layer = "policy"
        sec_cand.description = "Security policy rule adjustment"
        decision = self.ctrl.evaluate_promotion_eligibility(
            sec_cand, self.comparison, security_clean=True, approval_token=None
        )
        self.assertEqual(decision.outcome, PromotionOutcome.REJECTED_GATE_FAILURE)
        self.assertEqual(decision.approval_token_id, "missing_tier_c_token")

    def test_e16_92_promotion_tier_c_token_accepted(self):
        sec_cand = copy.deepcopy(self.cand)
        sec_cand.target_layer = "policy"
        sec_cand.description = "Security policy rule adjustment"
        decision = self.ctrl.evaluate_promotion_eligibility(
            sec_cand, self.comparison, security_clean=True, approval_token="token-supervisor-pass-123"
        )
        self.assertEqual(decision.outcome, PromotionOutcome.PROMOTED)
        self.assertEqual(decision.approval_token_id, "token-supervisor-pass-123")

    def test_e16_93_promotion_exports_quarantined_lesson(self):
        lesson = self.ctrl.export_quarantined_lesson(self.cand, rationale="Improved brevity on VAL_POOL by 4.2%")
        self.assertTrue(lesson["lesson_id"].startswith("lsn-"))
        self.assertEqual(lesson["quarantine_status"], "evaluated_safe")

    def test_e16_94_cas_lease_initial_acquisition(self):
        acquired, fence = self.store.acquire_eval_lease("run-lease-1", "worker-alpha", ttl_seconds=30.0)
        self.assertTrue(acquired)
        self.assertEqual(fence, 1)

    def test_e16_95_cas_lease_conflict_rejection(self):
        self.store.acquire_eval_lease("run-lease-2", "worker-alpha", ttl_seconds=30.0)
        acquired, fence = self.store.acquire_eval_lease("run-lease-2", "worker-beta", ttl_seconds=30.0)
        self.assertFalse(acquired)
        self.assertEqual(fence, 1)

    def test_e16_96_cas_lease_expiry_and_recovery(self):
        # Initial acquisition with 0 TTL (already expired)
        self.store.acquire_eval_lease("run-lease-3", "worker-alpha", ttl_seconds=0.0)
        time.sleep(0.01)
        # Worker beta acquires expired lease
        acquired, fence = self.store.acquire_eval_lease("run-lease-3", "worker-beta", ttl_seconds=30.0)
        self.assertTrue(acquired)
        self.assertEqual(fence, 2)


if __name__ == "__main__":
    unittest.main()
