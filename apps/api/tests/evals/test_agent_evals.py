"""
Test suite for HINAA OS Agent Evaluation & Reasoning Benchmark Suite.
"""

from __future__ import annotations

import json
import pytest
from hinaa_api.evaluation.agent_eval_runner import AgentEvalRunner, EVAL_BENCHMARK_CASES


@pytest.mark.asyncio
async def test_agent_eval_suite_execution(tmp_path):
    runner = AgentEvalRunner(output_dir=tmp_path / "evals")
    scorecard = await runner.run_full_suite()

    # Verify high compliance & pass rate
    assert scorecard.total_cases == len(EVAL_BENCHMARK_CASES)
    assert scorecard.passed_cases == scorecard.total_cases
    assert scorecard.pass_rate >= 95.0
    assert scorecard.overall_score >= 95.0

    # Verify category coverage
    categories = scorecard.category_scores
    assert "safety_guardrails" in categories
    assert "tool_selection" in categories
    assert "loop_verification" in categories
    assert "multilingual" in categories

    # Verify scorecard disk file was written
    scorecard_file = tmp_path / "evals" / "latest_scorecard.json"
    assert scorecard_file.exists()
    data = json.loads(scorecard_file.read_text(encoding="utf-8"))
    assert data["total_cases"] == scorecard.total_cases
    assert data["pass_rate"] == scorecard.pass_rate
