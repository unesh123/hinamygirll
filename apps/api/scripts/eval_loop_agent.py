"""Live eval runner for the loop agent step.

Runs the golden repair cases against a REAL configured provider and reports
accuracy, latency and token cost. Without a provider key it prints the exact
secret names to configure and exits non-zero.

Usage (from apps/api):
    python -m scripts.eval_loop_agent --turns 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hinaa_api.config import get_settings  # noqa: E402
from hinaa_api.harness.agent_step import LLMAgentStep, resolve_loop_provider  # noqa: E402
from hinaa_api.harness.loop_engine import LoopEngine, LoopTaskSpec  # noqa: E402

GOLDEN_CASES: List[Dict[str, Any]] = [
    {
        "name": "fix-answer-value",
        "setup": {"answer.txt": "41\n"},
        "reply_hint": "answer.txt must contain exactly 42",
        "expected": {"answer.txt": "42"},
        "max_turns": 3,
    },
    {
        "name": "create-missing-config",
        "setup": {},
        "reply_hint": "config.json must exist and contain {\"enabled\": true}",
        "expected": {"config.json": '{"enabled": true}'},
        "max_turns": 3,
    },
    {
        "name": "fix-python-assert",
        "setup": {"calc.py": "def add(a, b):\n    return a - b\n"},
        "reply_hint": "add(a, b) in calc.py must return a + b",
        "expected": {"calc.py": "def add(a, b):\n    return a + b\n"},
        "max_turns": 3,
    },
]


def _check(case: Dict[str, Any], workspace: Path) -> bool:
    for name, needle in case["expected"].items():
        path = workspace / name
        if not path.exists():
            return False
        if needle.strip() not in path.read_text(encoding="utf-8"):
            return False
    return True


async def run_case(case: Dict[str, Any], max_turns: int) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        workspace = Path(td) / "ws"
        workspace.mkdir()
        for name, content in case["setup"].items():
            path = workspace / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        spec = LoopTaskSpec(
            task_id=f"eval_{case['name']}",
            goal_title=case["reply_hint"],
            description=f"Success means: {case['reply_hint']}.",
            verification_command=["true"],  # scoring is by expected-content check below
            max_turns=max_turns,
            timeout_per_turn_seconds=120.0,
            workspace_dir=str(workspace),
        )
        llm_step = LLMAgentStep(
            provider=_PROVIDER,
            workspace_dir=workspace,
            trace_path=workspace / "trace.jsonl",
        )
        engine = LoopEngine(base_dir=workspace / "state")
        report = await engine.run_loop(spec, llm_step.as_engine_step(spec))
        passed = _check(case, workspace)
        trace_lines = (workspace / "trace.jsonl").read_text(encoding="utf-8").strip().splitlines()
        latencies = [json.loads(l).get("latency_ms", 0.0) for l in trace_lines if l.strip()]
        tokens_in = sum(json.loads(l).get("input_tokens", 0) for l in trace_lines if l.strip())
        tokens_out = sum(json.loads(l).get("output_tokens", 0) for l in trace_lines if l.strip())
        return {
            "name": case["name"],
            "passed": passed,
            "loop_status": report.status,
            "turns": report.total_turns,
            "latency_ms_avg": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=3)
    args = parser.parse_args()

    global _PROVIDER  # noqa: F824
    provider = resolve_loop_provider()
    if provider is None:
        print(
            "No LLM provider configured. Set one of these Vault/env secrets and rerun:\n"
            "  AGENT_ROUTER_API_KEY, ANTHROPIC_API_KEY (HINAA_CLAUDE_API_KEY), "
            "OPENAI_API_KEY, GROQ_API_KEY, GEMINI_API_KEY"
        )
        return 2
    _PROVIDER = provider
    print(f"Provider: {provider.name} model={provider.model}")

    results = [asyncio.run(run_case(case, args.turns)) for case in GOLDEN_CASES]
    passed = sum(1 for r in results if r["passed"])
    print("\nEval results:")
    for r in results:
        print(f"  {r['name']}: {'PASS' if r['passed'] else 'FAIL'} "
              f"({r['loop_status']}, {r['turns']} turns, avg latency {r['latency_ms_avg']} ms)")
    accuracy = passed / len(results)
    avg_latency = sum(r["latency_ms_avg"] for r in results) / len(results)
    tokens = sum(r["input_tokens"] + r["output_tokens"] for r in results)
    print(f"\nAccuracy: {passed}/{len(results)} ({accuracy:.0%}) | avg latency {avg_latency:.0f} ms | tokens {tokens}")
    return 0 if accuracy >= 0.66 else 1


_PROVIDER: Any = None  # set in main()

if __name__ == "__main__":
    raise SystemExit(main())
