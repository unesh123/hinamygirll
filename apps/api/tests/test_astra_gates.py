"""P1 Production Proof: Automated Test Suite for Gates 3, 4, and 5."""

import pytest
from hinaa_api.astra import (
    AstraInput,
    AstraRequest,
    AstraRoute,
    AstraRuntime,
    WorkspaceContext,
)


@pytest.mark.asyncio
async def test_gate3_router_matrix():
    runtime = AstraRuntime()

    # Case A: "hey hina"
    req_a = AstraRequest(conversation_id="c_case_a", input=AstraInput(text="hey hina"))
    events_a = [e async for e in runtime.stream_turn(req_a)]
    route_a = next(e for e in events_a if e.type == "route.decided")
    assert route_a.data["route"] == AstraRoute.CHAT.value
    plan_a = next(e for e in events_a if e.type == "plan")
    assert len(plan_a.data["plan"]["toolRequests"]) == 0

    # Case B: "who is Mikasa Ackerman?"
    req_b = AstraRequest(conversation_id="c_case_b", input=AstraInput(text="who is Mikasa Ackerman?"))
    events_b = [e async for e in runtime.stream_turn(req_b)]
    route_b = next(e for e in events_b if e.type == "route.decided")
    assert route_b.data["route"] == AstraRoute.CHAT.value
    ctx_b = next(e for e in events_b if e.type == "context.ready")
    assert "Mikasa Ackerman" in ctx_b.data["activeEntities"]

    # Case C: "show me images of Mikasa"
    req_c = AstraRequest(conversation_id="c_case_c", input=AstraInput(text="show me images of Mikasa"))
    events_c = [e async for e in runtime.stream_turn(req_c)]
    route_c = next(e for e in events_c if e.type == "route.decided")
    assert route_c.data["route"] == AstraRoute.DIRECT_ACTION.value
    assert any("image" in c for c in route_c.data["candidate_capabilities"])
    tool_c = next(e for e in events_c if e.type == "tool.started")
    assert "Mikasa Ackerman" in tool_c.data["parameters"]["query"]

    # Case D: "generate a cinematic image of Mikasa in Kathmandu"
    req_d = AstraRequest(
        conversation_id="c_case_d",
        input=AstraInput(text="generate a cinematic image of Mikasa in Kathmandu"),
    )
    events_d = [e async for e in runtime.stream_turn(req_d)]
    route_d = next(e for e in events_d if e.type == "route.decided")
    assert route_d.data["route"] == AstraRoute.DIRECT_ACTION.value
    assert "image.generate" in route_d.data["candidate_capabilities"]
    tool_d = next(e for e in events_d if e.type == "tool.started")
    assert tool_d.data["toolName"] == "image_generate"

    # Case E: "create a comprehensive document about Mikasa Ackerman"
    req_e = AstraRequest(
        conversation_id="c_case_e",
        input=AstraInput(text="create a comprehensive document about Mikasa Ackerman"),
    )
    events_e = [e async for e in runtime.stream_turn(req_e)]
    route_e = next(e for e in events_e if e.type == "route.decided")
    assert route_e.data["route"] == AstraRoute.DIRECT_ACTION.value
    assert "document.generate" in route_e.data["candidate_capabilities"]
    tool_e = next(e for e in events_e if e.type == "tool.started")
    assert tool_e.data["toolName"] == "document_generate"
    assert "Mikasa Ackerman" in tool_e.data["parameters"]["subject"]

    # Case F: "build me a premium Hina landing page"
    req_f = AstraRequest(
        conversation_id="c_case_f",
        input=AstraInput(text="build me a premium Hina landing page"),
    )
    events_f = [e async for e in runtime.stream_turn(req_f)]
    route_f = next(e for e in events_f if e.type == "route.decided")
    assert route_f.data["route"] == AstraRoute.WORKSPACE.value

    # Case G: "what does a reminder mean?"
    req_g = AstraRequest(
        conversation_id="c_case_g",
        input=AstraInput(text="what does a reminder mean?"),
    )
    events_g = [e async for e in runtime.stream_turn(req_g)]
    route_g = next(e for e in events_g if e.type == "route.decided")
    assert route_g.data["route"] == AstraRoute.CHAT.value

    # Case H: "remind me tomorrow at 8"
    req_h = AstraRequest(
        conversation_id="c_case_h",
        input=AstraInput(text="remind me tomorrow at 8"),
    )
    events_h = [e async for e in runtime.stream_turn(req_h)]
    route_h = next(e for e in events_h if e.type == "route.decided")
    assert route_h.data["route"] == AstraRoute.DIRECT_ACTION.value
    assert "reminders.create" in route_h.data["candidate_capabilities"]
    tool_h = next(e for e in events_h if e.type == "tool.started")
    assert tool_h.data["toolName"] == "create_reminder"

    # Case I: "make it better" (with no active referent)
    req_i = AstraRequest(
        conversation_id="c_case_i",
        input=AstraInput(text="make it better"),
    )
    events_i = [e async for e in runtime.stream_turn(req_i)]
    route_i = next(e for e in events_i if e.type == "route.decided")
    assert route_i.data["route"] == AstraRoute.CLARIFICATION.value


@pytest.mark.asyncio
async def test_gate4_entity_continuity_regression():
    runtime = AstraRuntime()
    convo_id = "c_mikasa_continuity"

    # Turn 1: "Who is Mikasa Ackerman?"
    t1 = [e async for e in runtime.stream_turn(AstraRequest(conversation_id=convo_id, input=AstraInput(text="Who is Mikasa Ackerman?")))]
    ctx1 = next(e for e in t1 if e.type == "context.ready")
    assert "Mikasa Ackerman" in ctx1.data["activeEntities"]

    # Turn 2: "Tell me more about her."
    t2 = [e async for e in runtime.stream_turn(AstraRequest(conversation_id=convo_id, input=AstraInput(text="Tell me more about her.")))]
    res2 = next(e for e in t2 if e.type == "entity.resolved")
    assert res2.data["canonical_name"] == "Mikasa Ackerman"

    # Turn 3: "Show me images."
    t3 = [e async for e in runtime.stream_turn(AstraRequest(conversation_id=convo_id, input=AstraInput(text="Show me images.")))]
    tool3 = next(e for e in t3 if e.type == "tool.started")
    assert "Mikasa Ackerman Attack on Titan" in tool3.data["parameters"]["query"]
    assert "Show me images" not in tool3.data["parameters"]["query"]

    # Turn 4: "Get me more of her."
    t4 = [e async for e in runtime.stream_turn(AstraRequest(conversation_id=convo_id, input=AstraInput(text="Get me more of her.")))]
    res4 = next(e for e in t4 if e.type == "entity.resolved")
    assert res4.data["canonical_name"] == "Mikasa Ackerman"

    # Turn 5: "Make a document about her."
    t5 = [e async for e in runtime.stream_turn(AstraRequest(conversation_id=convo_id, input=AstraInput(text="Make a document about her.")))]
    tool5 = next(e for e in t5 if e.type == "tool.started")
    assert tool5.data["toolName"] == "document_generate"
    assert "Mikasa Ackerman" in tool5.data["parameters"]["subject"]


@pytest.mark.asyncio
async def test_gate5_real_capability_execution():
    runtime = AstraRuntime()

    # Document generation creates real artifact event
    req = AstraRequest(
        conversation_id="c_doc_test",
        input=AstraInput(text="create a comprehensive document about Mikasa Ackerman"),
    )
    events = [e async for e in runtime.stream_turn(req)]
    types = [e.type for e in events]
    assert "tool.started" in types
    assert "tool.progress" in types
    assert "artifact.created" in types
    assert "tool.completed" in types

    art_event = next(e for e in events if e.type == "artifact.created")
    assert art_event.data["kind"] == "document"
    assert len(art_event.data["outline"]) == 5
    assert "Mikasa Ackerman" in art_event.data["title"]
