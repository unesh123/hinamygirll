"""
Comprehensive test suite for HINAA Cognitive Core & World State OS.
"""

import pytest
import time
from hinaa_api.cognitive import (
    CognitiveKernel,
    CognitiveRun,
    WorldModel,
    WorldState,
    ContextCompiler,
    MemoryConsolidator,
    SessionBridge,
    HinaEvent,
)
from hinaa_api.memory_v2.manager import MemoryManagerV2


def test_world_model_hydration_and_observation():
    state = WorldModel.hydrate_initial_state(user_id="test_user", working_dir="/test/dir")
    assert state.user.user_id == "test_user"
    assert state.device.platform in ("windows", "macos", "linux")
    assert state.filesystem.working_directory == "/test/dir"

    prompt_summary = WorldModel.summarize_for_prompt(state)
    assert "Operating System & Platform" in prompt_summary
    assert "Active Window & Application" in prompt_summary

    # Apply mock desktop observation
    class MockObs:
        active_window_title = "Visual Studio Code"
        active_process_name = "Code.exe"
        running_apps = ["Code.exe", "Spotify.exe"]
        media_playing = True
        vision = None

    updated = WorldModel.apply_desktop_observation(state, MockObs())
    assert updated.device.active_window == "Visual Studio Code"
    assert updated.app.active_app == "Code.exe"
    assert updated.app.media_playing is True
    assert "Code.exe" in updated.app.running_apps


def test_context_compiler_budget_and_ranking():
    compiler = ContextCompiler(default_token_budget=500)
    world = WorldModel.hydrate_initial_state(user_id="alice")

    mem_mgr = MemoryManagerV2()
    mem_mgr.remember(user_id="alice", content="User prefers dark theme in UI", category="preference")
    mem_mgr.remember(user_id="alice", content="User writes Python and TypeScript", category="fact")

    specs = {
        "architecture": "HINAA operates as an 8-OS frontier cognitive platform.",
        "active-plan": "Deliver canonical Cognitive Kernel and World State.",
    }

    recent_turns = [
        {"role": "user", "content": "How does the cognitive core work?"},
        {"role": "assistant", "content": "The cognitive core orchestrates world model, planning, and verification."},
    ]

    compiled = compiler.compile(
        query="Tell me about HINAA architecture and my theme preference",
        world_state=world,
        user_id="alice",
        memory_manager=mem_mgr,
        project_specs=specs,
        recent_turns=recent_turns,
        max_budget=800,
    )

    assert compiled.total_token_estimate <= 800
    assert "HINAA operates as an 8-OS" in compiled.project_context_block
    assert "User prefers dark theme" in compiled.memory_facts_block
    assert "Operating System & Platform" in compiled.world_state_block


def test_memory_consolidation_and_supersession():
    mem_mgr = MemoryManagerV2()
    user_id = "bob"

    # Turn 1: Initial preference
    c1 = MemoryConsolidator.consolidate_turn(
        user_id=user_id,
        user_text="I prefer dark mode in my editors.",
        assistant_text="Noted, dark mode is saved.",
        memory_manager=mem_mgr,
    )
    assert len(c1) >= 1
    active = mem_mgr.get_active_semantic_memories(user_id)
    assert any("dark mode" in f.content for f in active)

    # Turn 2: Conflicting preference
    c2 = MemoryConsolidator.consolidate_turn(
        user_id=user_id,
        user_text="I prefer light mode from now on.",
        assistant_text="Updated preference to light mode.",
        memory_manager=mem_mgr,
    )
    assert any(c["action"] == "superseded" for c in c2)
    active_after = mem_mgr.get_active_semantic_memories(user_id)
    assert any("light mode" in f.content for f in active_after)


def test_session_bridge_continuity(tmp_path):
    bridge = SessionBridge(root_dir=str(tmp_path))
    user_id = "charlie"

    summary = bridge.finalize_session(
        session_id="sess_001",
        user_id=user_id,
        decisions=["Adopt unified CognitiveRun state machine"],
        completed_tasks=["Implemented WorldState", "Implemented ContextCompiler"],
        unresolved_items=["Build real-time event streaming router"],
    )

    assert summary.session_id == "sess_001"
    assert "Adopt unified CognitiveRun state machine" in summary.key_decisions

    # Test bootstrap for session N+1
    bootstrap = bridge.bootstrap_new_session(user_id=user_id)
    assert bootstrap["has_prior_session"] is True
    assert bootstrap["last_session_id"] == "sess_001"
    assert "Build real-time event streaming router" in bootstrap["unresolved_items"]
    assert "Implemented WorldState" in bootstrap["current_state_markdown"]


@pytest.mark.asyncio
async def test_cognitive_kernel_execution(tmp_path):
    bridge = SessionBridge(root_dir=str(tmp_path))
    mem_mgr = MemoryManagerV2()
    kernel = CognitiveKernel(session_bridge=bridge, memory_manager=mem_mgr)

    events_received = []

    def on_event(evt: HinaEvent):
        events_received.append(evt)

    run = await kernel.execute_turn(
        text="Open notepad on my pc",
        user_id="dave",
        session_id="sess_live",
        event_callback=on_event,
    )

    assert run.status in ("completed", "executing")
    assert run.world_state is not None
    assert len(run.plan.nodes) >= 1
    assert run.verification.passed is True

    # Check event envelope emission
    event_types = [e.event_type for e in events_received]
    assert "turn.started" in event_types
    assert "world.hydrated" in event_types
    assert "context.compiled" in event_types
    assert "plan.generated" in event_types
    assert "run.completed" in event_types
