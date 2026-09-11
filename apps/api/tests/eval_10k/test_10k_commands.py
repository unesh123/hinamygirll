from __future__ import annotations

import pytest
from .generator import CommandGenerator
from .evaluator import CommandEvaluator


@pytest.mark.asyncio
async def test_10k_synthetic_command_evaluation():
    """Runs the 10,000-command synthetic evaluation suite across all 10 categories:

    1. text_to_image (1,000)
    2. image_to_image_reference (1,000)
    3. stock_and_web_search (1,000)
    4. upscale_and_enhance (1,000)
    5. relight_and_ambiance (1,000)
    6. multimodal_qa (1,000)
    7. multistep_workflows (1,000)
    8. fault_and_malformed_inputs (1,000)
    9. security_ssrf_and_injections (1,000)
    10. realtime_live_multimodal (1,000)

    Verifies 100% pass rate, zero dropped references, and strict SSRF blocking.
    """
    generator = CommandGenerator()
    commands = generator.generate_all(target_per_category=1000)
    assert len(commands) == 10000, f"Expected exactly 10,000 commands, got {len(commands)}"

    evaluator = CommandEvaluator()
    report = await evaluator.run_suite(commands)

    # Print summary diagnostics
    print(f"\n--- 10,000 COMMAND EVALUATION REPORT ---")
    print(f"Total Evaluated: {report.total_commands}")
    print(f"Passed: {report.passed_commands}")
    print(f"Failed: {report.failed_commands}")
    print(f"Overall Pass Rate: {report.overall_pass_rate:.2f}%")
    print(f"Execution Time: {report.elapsed_seconds:.2f}s")
    print("----------------------------------------")

    for cat_name, score in report.category_scores.items():
        print(f"  {cat_name:<30} {score.passed:>5}/{score.total:>5} ({score.pass_rate:>6.2f}%)")
        if score.failures:
            print(f"    Sample failure: {score.failures[0]}")

    # Assert 100% pass rate across the board
    assert report.failed_commands == 0, f"10k Evaluation had {report.failed_commands} failures! See output."
    assert report.overall_pass_rate == 100.0
