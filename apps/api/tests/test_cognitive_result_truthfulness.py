"""Regression evidence from Hina's failed launch reported as completed.

All execution and policy dependencies are test doubles. No PC application is
opened, no real approval is minted and no production session state is written.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest

from hinaa_api.cognitive.kernel import CognitiveKernel
from hinaa_api.cognitive.session_bridge import SessionBridge


def kernel_fixture(tmp_path, monkeypatch, result):
    import hinaa_api.tools.computer_operator as computer
    import hinaa_api.tools.intent_gate as intents
    monkeypatch.setattr(computer, "execute_computer_operator", AsyncMock(return_value=result))
    monkeypatch.setattr(intents, "sanction_tools", lambda _: SimpleNamespace(
        allowed={"computer_operator"}, parameters={"computer_operator": {"action": "open_application", "target": "test-editor"}},
    ))
    bridge = SessionBridge(root_dir=str(tmp_path))
    policy = SimpleNamespace(evaluate=Mock(return_value=SimpleNamespace(allowed=True)), record_audit=Mock())
    lake = SimpleNamespace(record_event=Mock(), archive_run=Mock(), flush_sync=Mock())
    return CognitiveKernel(session_bridge=bridge, policy_engine=policy, data_lake=lake, resilient_router=SimpleNamespace()), bridge


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [
    {"success": False, "detail": "Launch failed"},
    {"success": True, "verified": False, "detail": "Window never appeared"},
    {"success": True, "detail": "Process spawned; no verification supplied"},
    {"success": True, "verified": True, "data": None},
    "Launching test-editor...",
    None,
])
async def test_failed_or_unverified_tool_result_cannot_complete_or_enter_memory(tmp_path, monkeypatch, result):
    kernel, bridge = kernel_fixture(tmp_path, monkeypatch, result)
    events = []
    run = await kernel.execute_turn("Open test-editor", user_id="test-user", session_id="test-failure", event_callback=events.append)
    assert run.status == "failed"
    assert run.verification.passed is False
    assert run.plan.nodes[0].status == "failed"
    assert run.plan.nodes[0].error
    summary = bridge.get_latest_session_summary("test-user")
    assert summary.completed_tasks == []
    assert summary.unresolved_items
    markdown = (tmp_path / ".hina/current-state.md").read_text()
    assert "- [x]" not in markdown
    assert "step.failed" in [event.event_type for event in events]


@pytest.mark.asyncio
async def test_verified_success_is_the_only_tool_completion_case(tmp_path, monkeypatch):
    kernel, bridge = kernel_fixture(tmp_path, monkeypatch, {"success": True, "verified": True, "detail": "Observed test-editor window"})
    run = await kernel.execute_turn("Open test-editor", user_id="test-user", session_id="test-success")
    assert run.status == "completed"
    assert run.verification.passed
    summary = bridge.get_latest_session_summary("test-user")
    assert len(summary.completed_tasks) == 1
    assert summary.unresolved_items == []


def test_empty_session_does_not_invent_a_completed_task(tmp_path):
    bridge = SessionBridge(root_dir=str(tmp_path))
    bridge.finalize_session("empty-session", "test-user")
    markdown = (tmp_path / ".hina/current-state.md").read_text()
    assert "- [x]" not in markdown
    assert "General session activity" not in markdown


@pytest.mark.asyncio
async def test_unconnected_model_route_cannot_claim_a_response_was_generated(tmp_path, monkeypatch):
    kernel, bridge = kernel_fixture(tmp_path, monkeypatch, None)
    run = await kernel.execute_turn("Hello Hina", user_id="test-user", session_id="no-model")
    assert run.status == "failed"
    assert run.plan.nodes[0].error == "MODEL_EXECUTION_NOT_CONNECTED"
    assert bridge.get_latest_session_summary("test-user").completed_tasks == []
