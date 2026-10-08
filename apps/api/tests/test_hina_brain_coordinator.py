"""Comprehensive Unit Tests for HinaBrainCoordinator and Multi-Specialist Architecture."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from hinaa_api.brain.coordinator import HinaBrainCoordinator, BrainRunEvent
from hinaa_api.brain.specialists import (
    PlanningSpecialist,
    ResearchSpecialist,
    MemorySpecialist,
    CodingSpecialist,
    OperatorSpecialist,
    SynthesisSpecialist,
)


@pytest.mark.asyncio
async def test_planning_specialist_decomposition():
    planner = PlanningSpecialist()
    result = await planner.run(
        user_text="Build a FastAPI microservice for autonomous computer control in Python",
        intent_route=["planner", "coder", "operator", "synthesizer"],
    )
    assert "steps" in result
    assert len(result["steps"]) >= 4
    assert "software_engineering" in result["domains"]
    assert "risks" in result
    assert result["complexity"] in ("complex", "deep_research")


@pytest.mark.asyncio
async def test_coding_specialist_ast_validation():
    coder = CodingSpecialist()
    mock_executor = AsyncMock(return_value=None)
    result = await coder.run(
        user_text="Write a Python async task worker with error handling",
        tool_executor=mock_executor,
    )
    assert result["language"] == "python"
    assert result["syntax_valid"] is True
    assert "async def execute_task" in result["code"]
    assert len(result["test_cases"]) > 0


@pytest.mark.asyncio
async def test_memory_specialist_extraction():
    memory = MemorySpecialist()
    history = [
        {"role": "user", "content": "I am an IT student in Baneshwor building an AI startup."},
        {"role": "assistant", "content": "I believe in your vision!"},
    ]
    result = await memory.run(
        user_text="What should my next milestone be?",
        conversation_history=history,
        session_id="test-session",
    )
    assert len(result["key_facts"]) > 0
    assert any("Baneshwor" in f for f in result["key_facts"])
    assert len(result["context_snippets"]) == 2


@pytest.mark.asyncio
async def test_research_specialist_citations():
    researcher = ResearchSpecialist()
    mock_executor = AsyncMock()
    mock_executor.side_effect = lambda tool, args: {
        "results": [
            {"title": "Tech Hub Kathmandu", "url": "https://example.com/tech", "snippet": "Baneshwor is Nepal's core IT corridor.", "domain": "example.com"},
            {"title": "AI in Nepal 2026", "url": "https://example.com/ai", "snippet": "Nepal's tech ecosystem is booming.", "domain": "example.com"},
        ]
    }
    result = await researcher.run(
        user_text="Tell me about tech hubs in Baneshwor Nepal",
        tool_executor=mock_executor,
        available_tools=["web_search", "exa_search"],
    )
    assert result["source_count"] >= 1
    assert len(result["sources"]) >= 1
    assert "[1]" in result["synthesis"]


@pytest.mark.asyncio
async def test_operator_specialist_actuation():
    operator = OperatorSpecialist()
    mock_executor = AsyncMock(return_value={"success": True, "detail": "Navigated to target site"})
    result = await operator.run(
        user_text="browse to https://github.com",
        tool_executor=mock_executor,
        available_tools=["browser_execute_task", "computer_operator"],
    )
    assert result["success"] is True
    assert result["verified"] is True
    assert result["action"] == "browser_execute_task"


@pytest.mark.asyncio
async def test_synthesis_specialist_persona():
    synthesizer = SynthesisSpecialist()
    specialist_outputs = {
        "planner": {"steps": ["Step 1", "Step 2"]},
        "coder": {"code": "print('hello')", "language": "python"},
        "researcher": {
            "sources": [{"title": "Doc 1", "domain": "docs.com", "snippet": "Guide 2026"}],
            "synthesis": "[1] Guide 2026",
        },
    }
    result = await synthesizer.run(
        user_text="Help me build this",
        specialist_outputs=specialist_outputs,
    )
    text = result["response_text"]
    assert "Suno na babe" in text
    assert "### 🔍 Verified Research Intelligence" in text
    assert "### 💻 Technical Implementation" in text
    assert "### 🎯 Strategic Execution Roadmap" in text


@pytest.mark.asyncio
async def test_hina_brain_coordinator_full_stream():
    mock_executor = AsyncMock(return_value={"success": True, "detail": "Executed"})
    coordinator = HinaBrainCoordinator(tool_executor=mock_executor)

    events: list[BrainRunEvent] = []
    async for ev in coordinator.run_stream(
        turn_id="turn-test-1",
        user_text="Research the best AI APIs and write a Python script for computer use",
        available_tools=["web_search", "computer_operator"],
    ):
        events.append(ev)

    event_types = [e.event_type for e in events]
    assert "brain.run.started" in event_types
    assert "brain.specialist.started" in event_types
    assert "brain.specialist.completed" in event_types
    assert "brain.run.completed" in event_types
