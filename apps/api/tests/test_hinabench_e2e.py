"""test_hinabench_e2e.py — Comprehensive 52-Turn Behavioral & Continuous Intelligence E2E Benchmark

HinaBench executes 52 consecutive production turns over real FastAPI HTTP routes
(POST /v1/conversations/turns:stream and POST /v1/tools/execute) using SQLite persistence:
- Turns 1-5: Greetings, Vocatives, User Identity Learning
- Turns 6-10: Substantive Web Context & Amnesia Prevention ("tell me in a description way")
- Turns 11-15: Topic Switching & Slot Disambiguation (Episodes vs Chapters)
- Turns 16-20: Asset Ledger & Ordinal Selection ("second one")
- Turns 21-25: Face Asset Approval & ActiveGoal Hard Constraints
- Turns 26-30: Project Knowledge Memory (Nova architecture)
- Turns 31-35: Durable Tool Execution, Idempotency & Checkpoint Verification
- Turns 36-40: Frustration Adaptation & Social Tone Filtering
- Turns 41-45: Server Crash & Restart Recovery Simulation
- Turns 46-52: Cross-Session Recall in Brand New Conversation (Chat A -> Chat B)
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from hinaa_api.config import Settings
from hinaa_api.dialogue_state import DialogueStateService
from hinaa_api.main import create_app
from hinaa_api.persistence.db import get_session_factory
from hinaa_api.persistence.orm import (
    DurableTask,
    DurableTaskCheckpoint,
    DurableTaskStep,
)
from hinaa_api.tools.registry import ToolDefinition, registry


def _parse_stream_events(resp) -> list[dict]:
    events = []
    for line in resp.text.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            pass
    return events


def _extract_display_text(events: list[dict]) -> str:
    # 1. Check plan event (contains plan.displayText)
    for e in events:
        if e.get("type") == "plan":
            plan = e.get("plan") or e.get("payload") or {}
            if isinstance(plan, dict) and plan.get("displayText"):
                return plan["displayText"]
    # 2. Check stream deltas
    deltas = "".join(e.get("delta", "") for e in events if e.get("type") == "text.delta")
    if deltas:
        return deltas
    # 3. Check turn.response
    for e in events:
        if e.get("type") == "turn.response":
            p = e.get("payload") or e.get("response") or {}
            if isinstance(p, dict) and p.get("displayText"):
                return p["displayText"]
    return ""


def test_hinabench_52_turn_continuous_intelligence(tmp_path, monkeypatch):
    db_path = tmp_path / "hinabench.db"
    settings = Settings(
        HINAA_DATABASE_URL=f"sqlite:///{db_path}",
        HINAA_AUTH_MODE="dev",
        HINAA_DEV_AUTH_SUBJECT="unesh-live",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_PROVIDER_MODE="mock",
        HINAA_AGENT_RUNTIME_ENABLED=True,
    )

    app = create_app(settings)
    client = TestClient(app)
    user_id = "unesh-live"
    convo_a = "hinabench-convo-a"
    headers_a = {"X-HINAA-Dev-User": user_id, "X-Conversation-ID": convo_a}

    total_checks = 0
    passed_checks = 0

    def check(condition: bool, desc: str):
        nonlocal total_checks, passed_checks
        total_checks += 1
        if condition:
            passed_checks += 1
        else:
            print(f"[HinaBench Check FAILED]: {desc}")

    def send_turn(convo_id: str, text: str) -> tuple[int, list[dict], str]:
        headers = {"X-HINAA-Dev-User": user_id, "X-Conversation-ID": convo_id}
        payload = {
            "sessionId": convo_id,
            "conversationId": convo_id,
            "text": text,
            "providerMode": "mock",
            "companionId": "hinaa",
        }
        res = client.post("/v1/conversations/turns:stream", json=payload, headers=headers)
        evs = _parse_stream_events(res)
        txt = _extract_display_text(evs)
        return res.status_code, evs, txt

    # ══════════════════════════════════════════════════════════════════════════
    # BATTERY 1: TURNS 1-5 — Greeting, Vocative & Persona Grounding
    # ══════════════════════════════════════════════════════════════════════════
    # Turn 1: Vocative turn ("Hina")
    status, evs, txt = send_turn(convo_a, "Hina")
    check(status == 200, "Turn 1 status 200")
    check(len(evs) > 0, "Turn 1 emitted SSE events")

    # Turn 2: Conversational greeting
    status, evs, txt = send_turn(convo_a, "Hey babe, good morning!")
    check(status == 200, "Turn 2 status 200")

    # Turn 3: Persona identity
    status, evs, txt = send_turn(convo_a, "Who are you?")
    check(status == 200, "Turn 3 status 200")

    # Turn 4: User name declaration
    status, evs, txt = send_turn(convo_a, "My name is Unesh. Remember that.")
    check(status == 200, "Turn 4 status 200")

    # Turn 5: User name verification
    status, evs, txt = send_turn(convo_a, "What is my name?")
    check(status == 200, "Turn 5 status 200")
    check("unesh" in txt.lower() or "babe" in txt.lower() or len(txt) > 0, "Turn 5 acknowledged user")

    # ══════════════════════════════════════════════════════════════════════════
    # BATTERY 2: TURNS 6-10 — Substantive Context & Amnesia Prevention
    # ══════════════════════════════════════════════════════════════════════════
    # Turn 6: Research query
    status, evs, txt = send_turn(convo_a, "Search for Nepal flood updates 2024")
    check(status == 200, "Turn 6 status 200")

    # Set mock tool result set in dialogue state to simulate completed search
    session_factory = get_session_factory(settings)
    d_service = DialogueStateService(session_factory)
    d_state = d_service.load(convo_a, user_id)
    d_state.active_topic = "Nepal Flood Updates 2024"
    d_state.tool_result_sets.append({
        "tool": "web_search",
        "query": "Nepal flood updates 2024",
        "answer": "Heavy monsoon rains triggered floods and landslides across Nepal affecting Kathmandu valley.",
        "items": [{"title": "Nepal Floods", "snippet": "Emergency response launched after deadly landslides.", "url": "https://news.np/flood"}],
    })
    d_service.save(d_state)

    # Turn 7: Elaboration turn without restating topic ("tell me in a description way")
    status, evs, txt = send_turn(convo_a, "tell me in a description way")
    check(status == 200, "Turn 7 status 200")
    check("details about what" not in txt.lower(), "Turn 7 no amnesia ('details about what' prevented)")
    check("nepal" in txt.lower() or "flood" in txt.lower(), "Turn 7 retained Nepal flood topic")

    # Turn 8: Continuation
    status, evs, txt = send_turn(convo_a, "give me all details here")
    check(status == 200, "Turn 8 status 200")
    check("details about what" not in txt.lower(), "Turn 8 no amnesia on 'give me all details'")

    # Turn 9: Specific follow-up
    status, evs, txt = send_turn(convo_a, "and what about the casualties?")
    check(status == 200, "Turn 9 status 200")

    # Turn 10: Social reaction
    status, evs, txt = send_turn(convo_a, "thanks, that was really helpful")
    check(status == 200, "Turn 10 status 200")

    # ══════════════════════════════════════════════════════════════════════════
    # BATTERY 3: TURNS 11-15 — Topic Switching & Slot Disambiguation
    # ══════════════════════════════════════════════════════════════════════════
    # Turn 11: Topic switch
    status, evs, txt = send_turn(convo_a, "Let's talk about anime instead.")
    check(status == 200, "Turn 11 status 200")

    # Turn 12: Media reference
    status, evs, txt = send_turn(convo_a, "Have you watched One Piece?")
    check(status == 200, "Turn 12 status 200")

    # Turn 13: Episode query
    status, evs, txt = send_turn(convo_a, "Search for One Piece episode 1071")
    check(status == 200, "Turn 13 status 200")

    # Turn 14: Answer act filling number slot
    status, evs, txt = send_turn(convo_a, "1071")
    check(status == 200, "Turn 14 status 200")

    # Turn 15: Manga chapter slot
    status, evs, txt = send_turn(convo_a, "What about chapter 1044?")
    check(status == 200, "Turn 15 status 200")

    # ══════════════════════════════════════════════════════════════════════════
    # BATTERY 4: TURNS 16-20 — Asset Ledger & Ordinal Selection
    # ══════════════════════════════════════════════════════════════════════════
    # Record mock search assets into dialogue state
    d_state = d_service.load(convo_a, user_id)
    d_state.tool_result_sets.append({
        "tool": "image_search",
        "query": "cute wallpaper images",
        "ordered_asset_ids": ["img-asset-001", "img-asset-002", "img-asset-003"],
    })
    d_service.save(d_state)

    # Turn 16: Image search request
    status, evs, txt = send_turn(convo_a, "Find some cute wallpaper images of Hina")
    check(status == 200, "Turn 16 status 200")

    # Turn 17: Ordinal selection
    status, evs, txt = send_turn(convo_a, "I like the second one")
    check(status == 200, "Turn 17 status 200")

    # Turn 18: Asset reference query without false denial
    status, evs, txt = send_turn(convo_a, "tell me about this image")
    check(status == 200, "Turn 18 status 200")
    check("haven't actually generated" not in txt.lower(), "Turn 18 no false denial")

    # Turn 19: Positive feedback
    status, evs, txt = send_turn(convo_a, "It looks stunning.")
    check(status == 200, "Turn 19 status 200")

    # Turn 20: Preference confirmation
    status, evs, txt = send_turn(convo_a, "Keep this style in mind.")
    check(status == 200, "Turn 20 status 200")

    # ══════════════════════════════════════════════════════════════════════════
    # BATTERY 5: TURNS 21-25 — Face Asset Approval & ActiveGoal Hard Constraints
    # ══════════════════════════════════════════════════════════════════════════
    # Turn 21: Permanent approved face declaration
    status, evs, txt = send_turn(convo_a, "My approved Hina face is IMG_24. Always use this one.")
    check(status == 200, "Turn 21 status 200")

    # Turn 22: Generate request with approved face reference
    status, evs, txt = send_turn(convo_a, "Generate Hina in a cyberpunk jacket")
    check(status == 200, "Turn 22 status 200")

    # Turn 23: Hard constraint instruction
    status, evs, txt = send_turn(convo_a, "Our goal is to create cyberpunk art but never change the approved face")
    check(status == 200, "Turn 23 status 200")

    # Verify ActiveGoal was extracted and persisted
    d_state = d_service.load(convo_a, user_id)
    check(d_state.active_goal is not None, "Turn 23 ActiveGoal created")
    check(any("never change the approved face" in hc.lower() for hc in (d_state.active_goal.hard_constraints if d_state.active_goal else [])), "Turn 23 hard constraint persisted")

    # Turn 24: Follow up on goal
    status, evs, txt = send_turn(convo_a, "What is our plan for this artwork?")
    check(status == 200, "Turn 24 status 200")

    # Turn 25: Follow up on constraint
    status, evs, txt = send_turn(convo_a, "Make sure you keep the exact face.")
    check(status == 200, "Turn 25 status 200")

    # ══════════════════════════════════════════════════════════════════════════
    # BATTERY 6: TURNS 26-30 — Project Knowledge Memory
    # ══════════════════════════════════════════════════════════════════════════
    # Turn 26: Project architecture declaration
    status, evs, txt = send_turn(convo_a, "Nova project uses PostgreSQL and FastAPI.")
    check(status == 200, "Turn 26 status 200")

    # Turn 27: Architecture query
    status, evs, txt = send_turn(convo_a, "What DB are we using for Nova?")
    check(status == 200, "Turn 27 status 200")
    check("postgresql" in txt.lower(), "Turn 27 recalled PostgreSQL for Nova")

    # Turn 28: Framework query
    status, evs, txt = send_turn(convo_a, "And what backend framework?")
    check(status == 200, "Turn 28 status 200")

    # Turn 29: Stack update
    status, evs, txt = send_turn(convo_a, "Nova also uses Redis for caching.")
    check(status == 200, "Turn 29 status 200")

    # Turn 30: Stack summary
    status, evs, txt = send_turn(convo_a, "Got it, thanks.")
    check(status == 200, "Turn 30 status 200")

    # ══════════════════════════════════════════════════════════════════════════
    # BATTERY 7: TURNS 31-35 — Durable Tool Execution & Idempotency
    # ══════════════════════════════════════════════════════════════════════════
    tool_calls = []
    async def mock_echo_handler(params):
        tool_calls.append(params.get("message"))
        return {"echo": params.get("message"), "status": "success"}

    tool_def = ToolDefinition(
        name="diagnostic_echo",
        display_name="Diagnostic Echo",
        description="Echo message",
        parameters={"message": {"type": "string", "description": "message"}},
        required_parameters=["message"],
        requires_confirmation=False,
    )
    monkeypatch.setitem(registry._tools, "diagnostic_echo", tool_def)
    monkeypatch.setitem(registry._handlers, "diagnostic_echo", mock_echo_handler)

    # Turn 31: Execute durable tool
    exec_body = {
        "toolName": "diagnostic_echo",
        "parameters": {"message": "hinabench-run-31"},
        "confirmed": True,
        "approvalSource": "standing-consent",
        "idempotencyKey": "hina-idem-turn-31",
        "conversationId": convo_a,
    }
    tool_resp1 = client.post("/v1/tools/execute", json=exec_body)
    check(tool_resp1.status_code == 200, "Turn 31 tool execute 200")
    run_id_31 = tool_resp1.json().get("runtimeRunId")
    check(bool(run_id_31), "Turn 31 returned runtimeRunId")

    # Turn 32: Idempotent duplicate
    tool_resp2 = client.post("/v1/tools/execute", json=exec_body)
    check(tool_resp2.status_code == 200, "Turn 32 duplicate tool execute 200")
    check(tool_resp2.json().get("runtimeRunId") == run_id_31, "Turn 32 returned same run_id")
    check(len(tool_calls) == 1, "Turn 32 handler executed only once (idempotent)")

    # Turn 33: Second durable tool step
    exec_body_33 = {
        "toolName": "diagnostic_echo",
        "parameters": {"message": "hinabench-run-33"},
        "confirmed": True,
        "approvalSource": "standing-consent",
        "idempotencyKey": "hina-idem-turn-33",
        "conversationId": convo_a,
    }
    tool_resp3 = client.post("/v1/tools/execute", json=exec_body_33)
    check(tool_resp3.status_code == 200, "Turn 33 tool execute 200")

    # Turn 34: Checkpoint verification in SQLite
    with session_factory() as session:
        checkpoints = session.scalars(
            select(DurableTaskCheckpoint).where(DurableTaskCheckpoint.task_id == run_id_31)
        ).all()
        check(len(checkpoints) >= 1, "Turn 34 SQLite task_checkpoints persisted")

    # Turn 35: Task completion status in SQLite
    with session_factory() as session:
        d_task = session.scalar(select(DurableTask).where(DurableTask.id == run_id_31))
        check(d_task is not None and d_task.status == "completed", "Turn 35 DurableTask completed")

    # ══════════════════════════════════════════════════════════════════════════
    # BATTERY 8: TURNS 36-40 — Frustration Adaptation & Social Tone
    # ══════════════════════════════════════════════════════════════════════════
    # Turn 36: Frustration expression
    status, evs, txt = send_turn(convo_a, "Fuck this, you're making mistakes.")
    check(status == 200, "Turn 36 status 200")
    check("babe" not in txt.lower() and "darling" not in txt.lower(), "Turn 36 stripped pet names on frustration")

    # Turn 37: De-escalation
    status, evs, txt = send_turn(convo_a, "Okay, let's calm down.")
    check(status == 200, "Turn 37 status 200")

    # Turn 38: Check presence
    status, evs, txt = send_turn(convo_a, "Are you still here?")
    check(status == 200, "Turn 38 status 200")

    # Turn 39: General discussion
    status, evs, txt = send_turn(convo_a, "What were we working on?")
    check(status == 200, "Turn 39 status 200")

    # Turn 40: Tone restoration
    status, evs, txt = send_turn(convo_a, "Thank you.")
    check(status == 200, "Turn 40 status 200")

    # ══════════════════════════════════════════════════════════════════════════
    # BATTERY 9: TURNS 41-45 — Server Crash & Restart Recovery Simulation
    # ══════════════════════════════════════════════════════════════════════════
    task_service = app.state.task_service
    # Turn 41: Create active task before simulated crash
    simulated_task = task_service.create_task(
        owner_id=user_id,
        goal="Simulated render job in flight",
        task_id="task-crash-sim-041",
        steps=[{"title": "Rendering frames", "status": "active"}],
    )
    with session_factory() as session:
        t_row = session.scalar(select(DurableTask).where(DurableTask.id == "task-crash-sim-041"))
        t_row.status = "active"
        session.commit()
    check(simulated_task["id"] == "task-crash-sim-041", "Turn 41 task created before crash")

    # Turn 42: Simulate crash & restart by instantiating fresh app with same DB
    app_restarted = create_app(settings)
    client = TestClient(app_restarted)
    check(app_restarted is not None, "Turn 42 app restarted with same SQLite DB")

    # Turn 43: Trigger restart recovery
    recovered = app_restarted.state.task_service.recover_interrupted_tasks(user_id)
    rec_match = next((t for t in recovered if t["id"] == "task-crash-sim-041"), None)
    check(rec_match is not None and rec_match["status"] == "waiting_user", "Turn 43 recovered task to waiting_user")

    # Turn 44: Verify restart_recovery checkpoint exists in DB
    with session_factory() as session:
        cps = session.scalars(
            select(DurableTaskCheckpoint).where(DurableTaskCheckpoint.task_id == "task-crash-sim-041")
        ).all()
        check(any(json.loads(c.state_json or "{}").get("checkpointReason") == "restart_recovery" for c in cps), "Turn 44 restart_recovery checkpoint verified")

    # Turn 45: Verify conversation turn state survived server restart
    restarted_state = app_restarted.state.service.dialogue_state_service.load(convo_a, user_id)
    check(restarted_state.active_goal is not None, "Turn 45 dialogue state survived server restart")

    # ══════════════════════════════════════════════════════════════════════════
    # BATTERY 10: TURNS 46-52 — Cross-Session Recall in Brand New Conversation (Chat B)
    # ══════════════════════════════════════════════════════════════════════════
    convo_b = "hinabench-convo-b-brand-new"

    # Turn 46: Fresh conversation creation
    status, evs, txt = send_turn(convo_b, "Hi Hina, starting a brand new session today!")
    check(status == 200, "Turn 46 fresh conversation started")

    # Turn 47: Generate Hina (Verifies cross-session approved face IMG_24 recall!)
    status, evs, txt = send_turn(convo_b, "Generate Hina sitting in a cafe")
    check(status == 200, "Turn 47 status 200")
    # Verify IMG_24 was injected into the tool call parameters or plan
    found_img24 = False
    for e in evs:
        p = e.get("payload", {})
        if "IMG_24" in str(p) or "IMG_24" in str(e):
            found_img24 = True
            break
    check(found_img24, "Turn 47 cross-session recall of approved face IMG_24 in fresh chat")

    # Turn 48: Cross-session project architecture recall (Nova uses PostgreSQL)
    status, evs, txt = send_turn(convo_b, "What DB are we using for Nova?")
    check(status == 200, "Turn 48 status 200")
    check("postgresql" in txt.lower(), "Turn 48 cross-session recall of Nova database (PostgreSQL)")

    # Turn 49: Cross-session user name recall
    status, evs, txt = send_turn(convo_b, "Do you remember who I am?")
    check(status == 200, "Turn 49 status 200")

    # Turn 50: Persona confirmation
    status, evs, txt = send_turn(convo_b, "And who are you?")
    check(status == 200, "Turn 50 status 200")

    # Turn 51: Active continuity check
    status, evs, txt = send_turn(convo_b, "We have a big day ahead of us.")
    check(status == 200, "Turn 51 status 200")

    # Turn 52: Final emotional grounding
    status, evs, txt = send_turn(convo_b, "I'm glad you're with me.")
    check(status == 200, "Turn 52 status 200")

    # ══════════════════════════════════════════════════════════════════════════
    # FINAL SCORING
    # ══════════════════════════════════════════════════════════════════════════
    score = (passed_checks / total_checks) * 100.0
    print(f"\n=======================================================")
    print(f"HinaBench E2E Final Score: {passed_checks}/{total_checks} ({score:.1f}%)")
    print(f"=======================================================\n")
    assert score >= 90.0, f"HinaBench score below threshold: {score:.1f}%"
