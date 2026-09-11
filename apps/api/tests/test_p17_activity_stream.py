from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient


def test_activity_stream_lifecycle_events(client: TestClient):
    payload = {
        "sessionId": "test-activity-session",
        "text": "Hello HINAA, tell me about your capabilities",
        "companionId": "hinaa",
        "language": "mixed",
        "providerMode": "mock",
        "imageEngine": "gemini-3.5-flash-image",
        "voiceEngine": "elevenlabs",
    }
    response = client.post("/v1/conversations/turns:stream", json=payload)
    assert response.status_code == 200

    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    event_types = [e.get("type") for e in events]

    # Verify required lifecycle events are present
    assert "thinking" in event_types
    assert "run.started" in event_types
    assert "planning.started" in event_types
    assert "planning.completed" in event_types
    assert "run.completed" in event_types

    # thinking must be the FIRST event
    assert events[0]["type"] == "thinking"

    # Inspect run.started event contents
    run_started = next(e for e in events if e.get("type") == "run.started")
    assert run_started["imageEngine"] == "gemini-3.5-flash-image"
    assert run_started["voiceEngine"] == "elevenlabs"
    assert "runId" in run_started

    # Inspect run.completed event — check both possible field names
    run_completed = next(e for e in events if e.get("type") == "run.completed")
    assert "totalDurationMs" in run_completed or "latencyMs" in run_completed
    assert run_completed.get("totalDurationMs", run_completed.get("latencyMs", -1)) >= 0


def test_activity_stream_ordering(client: TestClient):
    """Verify the canonical event ordering: thinking → run.started → planning.* → plan → run.completed"""
    payload = {
        "sessionId": "test-ordering",
        "text": "Quick test",
        "companionId": "hinaa",
        "providerMode": "mock",
    }
    response = client.post("/v1/conversations/turns:stream", json=payload)
    assert response.status_code == 200

    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    event_types = [e.get("type") for e in events]

    # thinking must come before run.started
    assert event_types.index("thinking") < event_types.index("run.started")

    # run.started must come before planning.started
    if "planning.started" in event_types:
        assert event_types.index("run.started") < event_types.index("planning.started")

    # run.completed must be at the end
    assert event_types.index("run.completed") > event_types.index("run.started")


def test_activity_stream_with_tool_events(client: TestClient):
    """If tools are proposed, tool.started and tool.progress events must be emitted."""
    payload = {
        "sessionId": "test-tool-stream",
        "text": "Generate an image of a cybernetic sakura blossom",
        "companionId": "hinaa",
        "language": "mixed",
        "providerMode": "mock",
        "imageEngine": "comfyui-local",
    }
    response = client.post("/v1/conversations/turns:stream", json=payload)
    assert response.status_code == 200

    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    event_types = [e.get("type") for e in events]

    assert "run.started" in event_types
    assert "run.completed" in event_types

    # If tools were proposed, verify tool event chain
    plan_event = next((e for e in events if e.get("type") == "plan"), None)
    if plan_event and plan_event["plan"]["toolRequests"]:
        assert any(e.get("type") == "tool.started" for e in events)
        assert any(e.get("type") == "tool.progress" for e in events)


def test_activity_stream_run_completed_has_latency_ms(client: TestClient):
    """run.completed must contain latencyMs (the backend provider latency)."""
    payload = {
        "sessionId": "test-latency-check",
        "text": "Ping",
        "providerMode": "mock",
    }
    response = client.post("/v1/conversations/turns:stream", json=payload)
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    run_completed = next((e for e in events if e.get("type") == "run.completed"), None)
    assert run_completed is not None
    assert "latencyMs" in run_completed
    assert isinstance(run_completed["latencyMs"], (int, float))
    assert run_completed["latencyMs"] >= 0


def test_activity_stream_run_completed_has_total_duration_ms(client: TestClient):
    """run.completed must contain totalDurationMs (wall-clock from first yield)."""
    payload = {
        "sessionId": "test-total-duration",
        "text": "What is the time?",
        "providerMode": "mock",
    }
    response = client.post("/v1/conversations/turns:stream", json=payload)
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    run_completed = next((e for e in events if e.get("type") == "run.completed"), None)
    assert run_completed is not None
    assert "totalDurationMs" in run_completed
    assert isinstance(run_completed["totalDurationMs"], (int, float))
    assert run_completed["totalDurationMs"] >= 0


def test_assets_endpoint_accepts_image_png(client: TestClient):
    """POST /v1/assets accepts PNG images with 201."""
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0c"
        b"IDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00"
        b"\x00IEND\xaeB`\x82"
    )
    resp = client.post(
        "/v1/assets",
        files={"file": ("pixel.png", png_bytes, "image/png")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["kind"] == "image"
    assert data["mime_type"] == "image/png"


def test_assets_endpoint_accepts_text_plain(client: TestClient):
    """POST /v1/assets accepts plain text uploads."""
    text_bytes = b"Hello, HINAA universal document pipeline!"
    resp = client.post(
        "/v1/assets",
        files={"file": ("note.txt", text_bytes, "text/plain")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["kind"] in ("text", "document")
    assert "asset_id" in data


def test_assets_endpoint_returns_sha256_and_size(client: TestClient):
    """POST /v1/assets response must contain sha256 hash and size_bytes."""
    csv_content = b"x,y\n1,2\n3,4"
    resp = client.post(
        "/v1/assets",
        files={"file": ("data.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "sha256" in data
    assert len(data["sha256"]) == 64  # SHA256 hex is 64 chars
    assert "size_bytes" in data
    assert data["size_bytes"] == len(csv_content)

