from __future__ import annotations

import pytest

from hinaa_api.agent.agentic_runner import AgenticLoopRunner, DEFAULT_AGENTIC_TOOLS
from hinaa_api.agent.tool_labels import TOOL_DISPLAY_SPEC, describe_tool_call


def test_every_default_tool_has_human_label() -> None:
    for tool in DEFAULT_AGENTIC_TOOLS:
        assert tool in TOOL_DISPLAY_SPEC, f"{tool} missing explicit display label"
        desc = describe_tool_call(tool, {"path": "apps/web/src/App.tsx", "query": "test"})
        assert "_" not in desc["label"]
        assert desc["label"]
        assert desc["lane"] in {"reasoning", "research", "files", "media", "system"}


def test_describe_tool_call_extracts_basename_and_truncates() -> None:
    d = describe_tool_call("workspace_read_file", {"path": "apps/web/src/components/ChatPanel.tsx"})
    assert d == {"label": "Reading", "target": "ChatPanel.tsx", "lane": "files"}

    long_q = "x" * 120
    d2 = describe_tool_call("web_search", {"query": long_q})
    assert d2["label"] == "Searching web"
    assert len(d2["target"]) == 56
    assert d2["target"].endswith("...")


@pytest.mark.asyncio
async def test_runner_emits_parallel_group_and_only_real_thoughts() -> None:
    runner = AgenticLoopRunner(max_steps=4)
    events: list[tuple[str, dict]] = []

    async def on_event(name: str, payload: dict) -> None:
        events.append((name, payload))

    calls = 0

    async def planner(_transcript, _step):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "action": "call_tools",
                "rationale": "Checking package config and listing files in parallel.",
                "calls": [
                    {"tool": "workspace_list_dir", "arguments": {"path": "apps/web"}},
                    {"tool": "workspace_glob", "arguments": {"pattern": "apps/web/src/*.tsx"}},
                ],
            }
        # Step 2 intentionally omits rationale/thought -> must NOT emit fake thought event
        return {"action": "final", "summary": "Checked workspace files."}

    result = await runner.run(
        goal="Inspect frontend files",
        planner=planner,
        allowed_tools=["workspace_list_dir", "workspace_glob"],
        on_event=on_event,
    )
    assert result.status == "completed"
    thought_deltas = [p for n, p in events if n == "thought.delta"]
    assert len(thought_deltas) == 1
    assert "parallel" in thought_deltas[0]["text"]

    started = [p for n, p in events if n == "tool.started"]
    assert len(started) == 2
    assert started[0]["label"] == "Listing"
    assert started[1]["label"] == "Finding files"
    assert started[0]["parallelGroup"] == "batch-1"
    assert started[1]["parallelGroup"] == "batch-1"
