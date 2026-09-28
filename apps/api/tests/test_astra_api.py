"""Integration tests for Astra HTTP Streaming API endpoints."""

import pytest
from fastapi.testclient import TestClient
from hinaa_api.main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_astra_stream_endpoint(client):
    payload = {
        "conversation_id": "conv_api_test",
        "input": {
            "text": "remind me tomorrow at 3pm to review the quarterly report",
        },
    }
    response = client.post("/v1/astra/turns:stream", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    # Read SSE events from body
    lines = response.text.split("\n\n")
    events = []
    for chunk in lines:
        if chunk.startswith("data: "):
            import json
            data = json.loads(chunk[6:])
            events.append(data)

    types = [e.get("type") for e in events]
    assert "request.received" in types
    assert "context.compiling" in types
    assert "context.ready" in types
    assert "route.decided" in types
    assert "tool.started" in types
    assert "tool.completed" in types
    assert "plan" in types
    assert "run.completed" in types
