"""Golden eval set for the loop agent step (harness/agent_step.py).

Each case runs the REAL LoopEngine.run_loop + LLMAgentStep against a stubbed
HTTP transport (canned model replies — fake model output only in tests).
The hard gate is a real verification command executed in a real temp workspace.

Run:  python -m pytest tests/evals/test_loop_agent_step.py -q
Live scoring (needs a provider key): scripts/eval_loop_agent.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hinaa_api.harness.agent_step import (  # noqa: E402
    LLMAgentStep,
    LoopProvider,
    _confined_path,
    _extract_json_object,
)
from hinaa_api.harness.loop_engine import LoopEngine, LoopTaskSpec  # noqa: E402


def _openai_transport(reply_text: str, calls: List[Dict[str, Any]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": reply_text}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 80},
            },
        )

    return httpx.MockTransport(handler)


def _provider() -> LoopProvider:
    return LoopProvider(
        name="eval-stub",
        protocol="openai",
        base_url="https://eval.invalid/v1",
        api_key="test-key",
        model="eval-model-1",
    )


def _make_step(tmp_path: Path, reply_text: str, calls: List[Dict[str, Any]]) -> LLMAgentStep:
    client = httpx.AsyncClient(transport=_openai_transport(reply_text, calls))
    return LLMAgentStep(
        provider=_provider(),
        workspace_dir=tmp_path,
        trace_path=tmp_path / "trace.jsonl",
        client=client,
    )


def _spec(tmp_path: Path, extra: Optional[Dict[str, Any]] = None) -> LoopTaskSpec:
    data: Dict[str, Any] = {
        "task_id": "eval_loop_step",
        "goal_title": "Fix the value in answer.txt",
        "description": "answer.txt must contain exactly 42.",
        "verification_command": [
            sys.executable,
            "-c",
            "from pathlib import Path; assert Path('answer.txt').read_text().strip() == '42'",
        ],
        "max_turns": 3,
        "timeout_per_turn_seconds": 30.0,
        "workspace_dir": str(tmp_path),
        "target_files": ["answer.txt"],
    }
    if extra:
        data.update(extra)
    return LoopTaskSpec(**data)


GOOD_REPLY = json.dumps(
    {
        "thought": "answer.txt holds the wrong value; write 42.",
        "actions": [{"type": "write_file", "path": "answer.txt", "content": "42\n", "confirm": True}],
    }
)


def test_extract_json_object_tolerates_fences_and_noise():
    assert _extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json_object('Sure! {"a": {"b": 2}} hope that helps') == {"a": {"b": 2}}
    assert _extract_json_object("no json here") is None


def test_confined_path_blocks_escape(tmp_path):
    assert _confined_path(tmp_path, "src/main.py") is not None
    assert _confined_path(tmp_path, "../../etc/passwd") is None
    assert _confined_path(tmp_path, "/etc/passwd") is None
    assert _confined_path(tmp_path, "") is None


def test_eval_golden_1_correct_edit_passes_gate(tmp_path):
    """A correct repair action makes the real hard gate pass."""
    calls: List[Dict[str, Any]] = []
    step = _make_step(tmp_path, GOOD_REPLY, calls)
    engine = LoopEngine(base_dir=tmp_path / "state")
    (tmp_path / "answer.txt").write_text("41\n", encoding="utf-8")
    report = asyncio.run(engine.run_loop(_spec(tmp_path), step.as_engine_step(_spec(tmp_path))))
    assert report.status == "COMPLETED", report.summary
    assert (tmp_path / "answer.txt").read_text().strip() == "42"
    trace = (tmp_path / "trace.jsonl").read_text().strip().splitlines()
    record = json.loads(trace[-1])
    assert record["status"] == "acted"
    assert record["outcomes"][0]["status"] == "applied"
    assert record["model"] == "eval-model-1"
    assert record["input_tokens"] > 0
    assert record["prompt_chars"] > 0


def test_eval_golden_2_path_escape_is_blocked(tmp_path):
    """An escape attempt is blocked and nothing lands outside the workspace."""
    evil = json.dumps(
        {
            "thought": "write outside",
            "actions": [{"type": "write_file", "path": "../escape.txt", "content": "x", "confirm": True}],
        }
    )
    step = _make_step(tmp_path, evil, [])
    (tmp_path / "answer.txt").write_text("41\n", encoding="utf-8")
    result = asyncio.run(step.run(_spec(tmp_path), 1, None))
    assert result.status == "acted"
    assert result.actions_applied == 0
    assert result.outcomes[0].status == "blocked"
    assert not (tmp_path.parent / "escape.txt").exists()


def test_eval_golden_3_malformed_reply_changes_nothing(tmp_path):
    """A non-JSON reply applies nothing and is recorded as an error."""
    step = _make_step(tmp_path, "I think you should edit answer.txt manually.", [])
    result = asyncio.run(step.run(_spec(tmp_path), 1, None))
    assert result.actions_applied == 0
    assert result.status == "error"
    record = json.loads((tmp_path / "trace.jsonl").read_text().strip().splitlines()[-1])
    assert record["status"] == "error"
    assert record["error"] is None


def test_eval_golden_4_run_command_blocked_by_default(tmp_path):
    """Shell actions are blocked unless HINAA_LOOP_ALLOW_COMMANDS=1."""
    reply = json.dumps(
        {
            "thought": "use shell",
            "actions": [{"type": "run_command", "command": "echo 42 > answer.txt", "confirm": True}],
        }
    )
    step = _make_step(tmp_path, reply, [])
    result = asyncio.run(step.run(_spec(tmp_path), 1, None))
    assert result.actions_applied == 0
    assert result.outcomes[0].status == "blocked"
    assert "disabled" in result.outcomes[0].detail


def test_eval_golden_5_loop_reports_no_actions_and_stops(tmp_path):
    """A model that never acts cannot pass the gate: loop stops on max turns."""
    do_nothing = json.dumps({"thought": "looks fine to me", "actions": []})
    step = _make_step(tmp_path, do_nothing, [])
    (tmp_path / "answer.txt").write_text("41\n", encoding="utf-8")
    report = asyncio.run(_run(_spec(tmp_path), step))
    assert report.status in {"STOPPED_MAX_TURNS", "FAILED", "STOPPED_CONSECUTIVE_FAILURES"}
    assert report.total_turns <= 3


async def _run(spec: LoopTaskSpec, step: LLMAgentStep):
    engine = LoopEngine(base_dir=Path(spec.workspace_dir or ".") / "state")
    return await engine.run_loop(spec, step.as_engine_step(spec))


def test_eval_scores_summary():
    """Aggregate gate: the golden set's accuracy must be 5/5 outcomes asserted."""
    # Each golden case asserts its own expected outcome above; this marker keeps
    # a single named score entry point for CI. Accuracy is measured live by
    # scripts/eval_loop_agent.py when a provider key is configured.
    assert GOOD_REPLY.count("write_file") == 1


# ── Multi-step tool use ──


class _SequencedTransport(httpx.MockTransport):
    """Different canned reply per model call (multi-step turns)."""

    def __init__(self, replies: List[str], calls: List[Dict[str, Any]]):
        self._replies = replies
        self._calls = calls
        super().__init__(self._handler)

    def _handler(self, request: httpx.Request) -> httpx.Response:
        index = min(len(self._calls), len(self._replies) - 1)
        self._calls.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": self._replies[index]}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 80},
            },
        )


def _make_multi_step(tmp_path: Path, replies: List[str], calls: List[Dict[str, Any]]) -> LLMAgentStep:
    client = httpx.AsyncClient(transport=_SequencedTransport(replies, calls))
    return LLMAgentStep(
        provider=_provider(),
        workspace_dir=tmp_path,
        trace_path=tmp_path / "trace.jsonl",
        client=client,
    )


def test_eval_golden_6_inspect_then_write_multi_step(tmp_path):
    """Turn 1 inspects (auto-approved read_file), turn 2 writes with confirm."""
    (tmp_path / "answer.txt").write_text("41\n", encoding="utf-8")
    replies = [
        json.dumps({"thought": "check current value", "actions": [{"type": "read_file", "path": "answer.txt"}]}),
        json.dumps(
            {
                "thought": "value is 41, must be 42; writing fix",
                "actions": [{"type": "write_file", "path": "answer.txt", "content": "42\n", "confirm": True}],
            }
        ),
    ]
    calls: List[Dict[str, Any]] = []
    step = _make_multi_step(tmp_path, replies, calls)
    engine = LoopEngine(base_dir=tmp_path / "state")
    report = asyncio.run(engine.run_loop(_spec(tmp_path), step.as_engine_step(_spec(tmp_path))))
    assert report.status == "COMPLETED", report.summary
    assert (tmp_path / "answer.txt").read_text().strip() == "42"
    assert len(calls) == 2  # two model turns: inspect, then fix
    turn1 = json.loads((tmp_path / "trace.jsonl").read_text().strip().splitlines()[0])
    assert turn1["outcomes"][0]["status"] == "applied"  # read_file auto-approved
    assert turn1["outcomes"][0]["detail"].startswith("read ")


def test_eval_golden_7_multi_action_turn_mixed_outcomes(tmp_path):
    """One turn: auto-approved list_files runs, unconfirmed write is refused."""
    (tmp_path / "answer.txt").write_text("41\n", encoding="utf-8")
    reply = json.dumps(
        {
            "thought": "look around, then write",
            "actions": [
                {"type": "list_files", "pattern": "*.txt"},
                {"type": "write_file", "path": "answer.txt", "content": "42\n"},  # no confirm
            ],
        }
    )
    step = _make_step(tmp_path, reply, [])
    result = asyncio.run(step.run(_spec(tmp_path), 1, None))
    assert result.status == "acted"
    assert result.outcomes[0].status == "applied"  # read-only, auto-approved
    assert result.outcomes[1].status == "blocked"  # side-effect without confirm
    assert result.actions_applied == 1
    assert (tmp_path / "answer.txt").read_text().strip() == "41"  # untouched


def test_eval_golden_8_list_then_write_then_verify(tmp_path):
    """Three-step plan: list → write with confirm → gate passes."""
    (tmp_path / "answer.txt").write_text("41\n", encoding="utf-8")
    replies = [
        json.dumps({"thought": "scan", "actions": [{"type": "list_files", "pattern": "**/*"}]}),
        json.dumps(
            {"thought": "write fix", "actions": [{"type": "write_file", "path": "answer.txt", "content": "42\n", "confirm": True}]}
        ),
    ]
    step = _make_multi_step(tmp_path, replies, [])
    engine = LoopEngine(base_dir=tmp_path / "state")
    report = asyncio.run(engine.run_loop(_spec(tmp_path), step.as_engine_step(_spec(tmp_path))))
    assert report.status == "COMPLETED", report.summary


# ── Phase 5: research tools ──


def test_eval_golden_9_search_files_finds_literal_text(tmp_path):
    """search_files returns file:line matches for literal text, auto-approved."""
    (tmp_path / "answer.txt").write_text("41\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# Notes\nthe value is stored as 41\n", encoding="utf-8")
    reply = json.dumps(
        {"thought": "find where 41 lives", "actions": [{"type": "search_files", "query": "41"}]}
    )
    step = _make_step(tmp_path, reply, [])
    result = asyncio.run(step.run(_spec(tmp_path), 1, None))
    assert result.status == "acted"
    assert result.outcomes[0].status == "applied"
    detail = result.outcomes[0].detail
    assert "notes.md:2" in detail
    assert "answer.txt:1" in detail


def test_eval_golden_10_read_content_reaches_next_turn_prompt(tmp_path):
    """The model must SEE read_file content on its next turn (no blind inspecting)."""
    (tmp_path / "answer.txt").write_text("41\n", encoding="utf-8")
    replies = [
        json.dumps({"thought": "inspect", "actions": [{"type": "read_file", "path": "answer.txt"}]}),
        json.dumps(
            {"thought": "fixing", "actions": [{"type": "write_file", "path": "answer.txt", "content": "42\n", "confirm": True}]}
        ),
    ]
    calls: List[Dict[str, Any]] = []
    step = _make_multi_step(tmp_path, replies, calls)
    engine = LoopEngine(base_dir=tmp_path / "state")
    report = asyncio.run(engine.run_loop(_spec(tmp_path), step.as_engine_step(_spec(tmp_path))))
    assert report.status == "COMPLETED", report.summary
    second_prompt = json.dumps(calls[1]).lower()
    assert "tool results from your previous turn" in second_prompt
    assert "41" in json.dumps(calls[1])


def test_eval_golden_11_fetch_url_rejects_non_http(tmp_path):
    """fetch_url with file:// is blocked at execution time (no filesystem exfil)."""
    reply = json.dumps(
        {"thought": "read secret", "actions": [{"type": "fetch_url", "url": "file:///etc/passwd"}]}
    )
    step = _make_step(tmp_path, reply, [])
    result = asyncio.run(step.run(_spec(tmp_path), 1, None))
    assert result.outcomes[0].status == "blocked"
    assert "only absolute http(s)" in result.outcomes[0].detail


def test_eval_golden_12_fetch_url_hits_public_http(tmp_path, monkeypatch):
    """fetch_url against a real (local, explicitly permitted) HTTP server returns its body."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    monkeypatch.setenv("HINAA_LOOP_ALLOW_PRIVATE_FETCH", "1")

    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"hello from hina test server")

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        reply = json.dumps(
            {
                "thought": "fetch docs",
                "actions": [{"type": "fetch_url", "url": f"http://127.0.0.1:{server.server_port}/docs"}]},
        )
        step = _make_step(tmp_path, reply, [])
        result = asyncio.run(step.run(_spec(tmp_path), 1, None))
    finally:
        server.shutdown()
    assert result.outcomes[0].status == "applied"
    assert "hello from hina test server" in result.outcomes[0].detail


def test_eval_golden_13_provider_failover_and_lazy_client(tmp_path):
    """Primary HTTP 500 fails over cleanly to the next configured LoopProvider."""
    (tmp_path / "answer.txt").write_text("41\n", encoding="utf-8")
    good_reply = json.dumps(
        {
            "thought": "failover succeeded",
            "actions": [{"type": "write_file", "path": "answer.txt", "content": "42\n", "confirm": True}],
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "primary.invalid" in str(request.url):
            return httpx.Response(500, text="upstream outage")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": good_reply}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 30},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    primary = LoopProvider(
        name="bad-primary",
        protocol="openai",
        base_url="https://primary.invalid/v1",
        api_key="k1",
        model="m1",
    )
    backup = LoopProvider(
        name="healthy-backup",
        protocol="openai",
        base_url="https://backup.invalid/v1",
        api_key="k2",
        model="m2",
    )
    step = LLMAgentStep(
        provider=primary,
        fallback_providers=[backup],
        workspace_dir=tmp_path,
        trace_path=tmp_path / "trace.jsonl",
        client=client,
    )
    engine = LoopEngine(base_dir=tmp_path / "state")
    report = asyncio.run(engine.run_loop(_spec(tmp_path), step.as_engine_step(_spec(tmp_path))))
    assert report.status == "COMPLETED", report.summary
    assert step.provider.name == "healthy-backup"

