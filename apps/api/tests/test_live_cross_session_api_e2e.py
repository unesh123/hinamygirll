"""test_live_cross_session_api_e2e.py — Real Live API Cross-Session Continuity Benchmark

Tests against the real production FastAPI router (POST /v1/conversations/turns:stream):
1. Chat A: User declares approved face reference -> Chat B (fresh conversation): User asks to generate Hina ->
   Verifies that IMG_24 is retrieved across sessions and bound to the tool request / prompt.
2. Chat C: User declares project architecture (Nova uses PostgreSQL) -> Chat D (fresh conversation):
   User asks what DB Nova uses -> Verifies that PostgreSQL is recalled across sessions.
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.main import create_app


@pytest.fixture
def api_client(tmp_path):
    db_path = tmp_path / "live_e2e.db"
    settings = Settings(
        HINAA_DATABASE_URL=f"sqlite:///{db_path}",
        HINAA_AUTH_MODE="dev",
        HINAA_DEV_AUTH_SUBJECT="test-user-live",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_PROVIDER_MODE="mock",
        HINAA_AGENT_RUNTIME_ENABLED=True,
    )
    app = create_app(settings)
    client = TestClient(app)
    return client


def _parse_stream_events(response) -> list[dict]:
    """Parse SSE lines into list of event dicts."""
    events = []
    for line in response.text.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            pass
    return events


def test_e2e_approved_face_cross_session_recall(api_client):
    """Chat A: Set approved face -> Close -> Chat B: Generate Hina again -> Verified IMG_24 attached."""
    # ── 1. Turn 1 (Conversation A): User sets permanent face reference ──
    convo_a = "convo-e2e-alpha-1"
    headers = {"X-HINAA-Dev-User": "test-user-live", "X-Conversation-ID": convo_a}
    payload_a = {
        "sessionId": convo_a,
        "conversationId": convo_a,
        "text": "My approved Hina face is IMG_24. Always use this one.",
        "providerMode": "mock",
        "companionId": "hinaa",
    }
    resp_a = api_client.post("/v1/conversations/turns:stream", json=payload_a, headers=headers)
    assert resp_a.status_code == 200
    events_a = _parse_stream_events(resp_a)
    assert any(e.get("type") in ("run.completed", "plan") for e in events_a)

    # ── 2. Turn 2 (Conversation B - Brand New Session): Ask to generate Hina ──
    convo_b = "convo-e2e-beta-2"
    headers_b = {"X-HINAA-Dev-User": "test-user-live", "X-Conversation-ID": convo_b}
    payload_b = {
        "sessionId": convo_b,
        "conversationId": convo_b,
        "text": "Generate Hina sitting in a cafe",
        "providerMode": "mock",
        "companionId": "hinaa",
    }
    resp_b = api_client.post("/v1/conversations/turns:stream", json=payload_b, headers=headers_b)
    assert resp_b.status_code == 200
    events_b = _parse_stream_events(resp_b)

    # Find the plan event in Chat B
    plan_event = next((e for e in events_b if e.get("type") == "plan"), None)
    assert plan_event is not None, "Did not receive a plan event in Chat B"
    plan_data = plan_event.get("plan", {})
    tool_requests = plan_data.get("toolRequests", [])

    # Verify that image_generate was requested and bound IMG_24 as reference image!
    img_req = next((t for t in tool_requests if t.get("toolName") == "image_generate"), None)
    assert img_req is not None, f"Expected image_generate toolRequest, got {tool_requests}"
    ref_imgs = img_req.get("parameters", {}).get("reference_images", [])
    assert "IMG_24" in ref_imgs, f"Expected IMG_24 in reference_images, got {ref_imgs}"


def test_e2e_project_architecture_cross_session_recall(api_client):
    """Chat C: Set project stack -> Close -> Chat D: Ask what DB Nova uses -> Recalled PostgreSQL."""
    # ── 1. Turn 1 (Conversation C): User declares project stack ──
    convo_c = "convo-e2e-gamma-3"
    headers_c = {"X-HINAA-Dev-User": "test-user-live", "X-Conversation-ID": convo_c}
    payload_c = {
        "sessionId": convo_c,
        "conversationId": convo_c,
        "text": "Nova project uses PostgreSQL.",
        "providerMode": "mock",
        "companionId": "hinaa",
    }
    resp_c = api_client.post("/v1/conversations/turns:stream", json=payload_c, headers=headers_c)
    assert resp_c.status_code == 200

    # ── 2. Turn 2 (Conversation D - Brand New Session): Ask about database ──
    convo_d = "convo-e2e-delta-4"
    headers_d = {"X-HINAA-Dev-User": "test-user-live", "X-Conversation-ID": convo_d}
    payload_d = {
        "sessionId": convo_d,
        "conversationId": convo_d,
        "text": "What DB are we using on Nova?",
        "providerMode": "mock",
        "companionId": "hinaa",
    }
    resp_d = api_client.post("/v1/conversations/turns:stream", json=payload_d, headers=headers_d)
    assert resp_d.status_code == 200
    events_d = _parse_stream_events(resp_d)

    # Verify that the response includes PostgreSQL
    plan_event = next((e for e in events_d if e.get("type") == "plan"), None)
    assert plan_event is not None
    plan_data = plan_event.get("plan", {})
    display_text = plan_data.get("displayText", "")

    # Also check deltas if any
    deltas = "".join(e.get("delta", "") for e in events_d if e.get("type") == "text.delta")
    combined_text = f"{display_text} {deltas}"
    assert "postgresql" in combined_text.lower(), f"Expected 'PostgreSQL' in response, got: {combined_text}"
