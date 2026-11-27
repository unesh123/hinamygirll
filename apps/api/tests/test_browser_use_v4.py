"""Unit tests for Browser-Use Cloud v4 endpoint routing, domain locking, and yellow/red gating."""

from __future__ import annotations

import json
import httpx
import pytest

from hinaa_api.config import Settings
from hinaa_api.main import create_app


@pytest.mark.asyncio
async def test_browser_use_v4_runs_queue_and_risk_gate(monkeypatch) -> None:
    monkeypatch.setenv("BROWSER_USE_API_KEY", "bu_test_12345")
    monkeypatch.setenv("BROWSER_USE_BASE_URL", "https://www.browserbase.com/")
    seen_calls: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        seen_calls.append((request.method, str(request.url), body))
        if request.method == "POST" and request.url.path == "/api/v4/runs":
            return httpx.Response(201, json={"runId": "run_v4_1", "sessionId": "sess_v4_1", "status": "completed", "output": "Checked prices"})
        if request.method == "POST" and request.url.path == "/api/v4/sessions/sess_v4_1/queue":
            return httpx.Response(202, json={"sessionId": "sess_v4_1", "status": "queued"})
        return httpx.Response(502, text="<html><body><h1>502 Bad Gateway</h1><script>noise</script></body></html>")

    orig_client = httpx.AsyncClient
    monkeypatch.setattr("hinaa_api.tools.browser_cloud.httpx.AsyncClient", lambda **kw: orig_client(transport=httpx.MockTransport(handler), **kw))

    settings = Settings(_env_file=None, provider_mode="mock")
    assert settings.active_browser_use_base_url == "https://api.browser-use.com/api/v4"
    app = create_app(settings)
    async with orig_client(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Yellow/red gating blocks checkout without confirmed=true
        gate_resp = await client.post(
            "/api/v4/runs",
            json={"task": "Checkout and purchase headphones on amazon.com", "allowed_domains": ["amazon.com"]},
        )
        assert gate_resp.status_code == 409
        assert gate_resp.json()["detail"]["risk_tier"] == "red"

        # 2. Green read-only run submits to /api/v4/runs with allowedDomains
        run_resp = await client.post(
            "/api/v4/runs",
            json={"task": "Compare Sony XM5 prices", "allowed_domains": ["Amazon.com", "BestBuy.com"]},
        )
        assert run_resp.status_code == 200, run_resp.text
        data = run_resp.json()
        assert data["run_id"] == "run_v4_1"
        assert data["session_id"] == "sess_v4_1"
        assert seen_calls[0][1] == "https://api.browser-use.com/api/v4/runs"
        assert seen_calls[0][2]["allowedDomains"] == ["amazon.com", "bestbuy.com"]

        # 3. Follow-up queues into /api/v4/sessions/sess_v4_1/queue
        q_resp = await client.post(
            "/api/v4/sessions/sess_v4_1/queue",
            json={"task": "Open customer reviews tab"},
        )
        assert q_resp.status_code == 200, q_resp.text
        assert q_resp.json()["status"] == "queued"
        assert seen_calls[1][1] == "https://api.browser-use.com/api/v4/sessions/sess_v4_1/queue"

    from hinaa_api.tools.browser_cloud import _sanitize_cloud_error

    sanitized = _sanitize_cloud_error(502, "<html><head><title>Bad Gateway</title></head><body><h1>502 Bad Gateway</h1></body></html>")
    assert "<html" not in sanitized.lower()
    assert "502 Bad Gateway" in sanitized
