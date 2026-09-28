"""Tests for HINA ASTRA — Core Cognitive Runtime & Subsystems."""

import pytest
from hinaa_api.astra import (
    AstraInput,
    AstraRequest,
    AstraRoute,
    AstraRuntime,
    ClientInfo,
    WorkspaceContext,
)


@pytest.mark.asyncio
async def test_astra_reminder_direct_action():
    runtime = AstraRuntime()
    request = AstraRequest(
        conversation_id="conv_test_1",
        input=AstraInput(text="remind me tomorrow at 5pm to buy groceries"),
    )

    events = []
    async for event in runtime.stream_turn(request):
        events.append(event)

    types = [e.type for e in events]
    assert "request.received" in types
    assert "context.compiling" in types
    assert "context.ready" in types
    assert "route.decided" in types

    route_event = next(e for e in events if e.type == "route.decided")
    assert route_event.data["route"] == AstraRoute.DIRECT_ACTION.value

    # Verify honest tool telemetry
    assert "tool.started" in types
    assert "tool.completed" in types
    tool_start = next(e for e in events if e.type == "tool.started")
    assert tool_start.data["toolName"] == "create_reminder"
    assert "buy groceries" in tool_start.data["parameters"]["title"]

    # Verify plan emission
    assert "plan" in types
    plan_event = next(e for e in events if e.type == "plan")
    assert len(plan_event.data["plan"]["toolRequests"]) == 1
    assert plan_event.data["plan"]["toolRequests"][0]["toolName"] == "create_reminder"

    # Verify run completed
    assert "run.completed" in types


@pytest.mark.asyncio
async def test_astra_image_direct_action():
    runtime = AstraRuntime()
    request = AstraRequest(
        conversation_id="conv_test_2",
        input=AstraInput(text="generate a high quality illustration of a cyberpunk city"),
    )

    events = []
    async for event in runtime.stream_turn(request):
        events.append(event)

    types = [e.type for e in events]
    assert "route.decided" in types
    route_event = next(e for e in events if e.type == "route.decided")
    assert route_event.data["route"] == AstraRoute.DIRECT_ACTION.value

    # Verify tool execution
    tool_start = next(e for e in events if e.type == "tool.started")
    assert tool_start.data["toolName"] == "image_generate"
    assert "cyberpunk city" in tool_start.data["parameters"]["prompt"]

    assert "plan" in types
    assert "run.completed" in types


@pytest.mark.asyncio
async def test_astra_chat_flow():
    runtime = AstraRuntime()
    request = AstraRequest(
        conversation_id="conv_test_3",
        input=AstraInput(text="Hello Hina, how are you feeling today?"),
    )

    events = []
    async for event in runtime.stream_turn(request):
        events.append(event)

    types = [e.type for e in events]
    route_event = next(e for e in events if e.type == "route.decided")
    assert route_event.data["route"] == AstraRoute.CHAT.value

    assert "text.delta" in types
    assert "plan" in types
    assert "run.completed" in types


@pytest.mark.asyncio
async def test_astra_workspace_route():
    runtime = AstraRuntime()
    request = AstraRequest(
        conversation_id="conv_test_4",
        input=AstraInput(text="fix the linter error in this file"),
        workspace=WorkspaceContext(
            workspace_id="ws_main",
            active_file="src/App.tsx",
        ),
    )

    events = []
    async for event in runtime.stream_turn(request):
        events.append(event)

    types = [e.type for e in events]
    route_event = next(e for e in events if e.type == "route.decided")
    assert route_event.data["route"] == AstraRoute.WORKSPACE.value
    assert "workspace.action.started" in types


@pytest.mark.asyncio
async def test_astra_grounded_pronoun_resolution_in_turn():
    runtime = AstraRuntime()
    convo_id = "conv_entity_continuity"

    # Turn 1: Mikasa mentioned
    req1 = AstraRequest(
        conversation_id=convo_id,
        input=AstraInput(text="I really admire Mikasa Ackerman from Attack on Titan."),
    )
    async for _ in runtime.stream_turn(req1):
        pass

    # Turn 2: Deictic pronoun reference
    req2 = AstraRequest(
        conversation_id=convo_id,
        input=AstraInput(text="generate a wallpaper of her in battle"),
    )

    events = []
    async for event in runtime.stream_turn(req2):
        events.append(event)

    types = [e.type for e in events]
    assert "entity.resolved" in types
    resolved_event = next(e for e in events if e.type == "entity.resolved")
    assert resolved_event.data["canonical_name"] == "Mikasa Ackerman"

    # Verify that the tool receives the grounded entity query
    tool_start = next(e for e in events if e.type == "tool.started")
    assert tool_start.data["toolName"] == "image_generate"
    # Grounded prompt must contain Mikasa Ackerman
    assert "Mikasa Ackerman" in tool_start.data["parameters"]["prompt"]
