import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest


spec = importlib.util.spec_from_file_location("configured_chat_check", Path(__file__).resolve().parents[3] / "scripts/check_configured_chat.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize("status,body,expected", [
    (200, 'data: {"choices":[{"delta":{"content":"Pong"}}]}\n\n', "responding"),
    (200, 'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n', "no_text"),
    (200, 'data: {"error":{"message":"test-secret"}}\n\n', "stream_error"),
    (401, '{"error":"test-secret"}', "rejected"),
])
async def test_probe_requires_actual_text_and_never_prints_secrets(status, body, expected, capsys):
    def handle(request):
        assert request.headers["Authorization"] == "Bearer test-secret"
        assert json.loads(request.content)["model"] == "wire-model"
        return httpx.Response(status, text=body)

    provider = SimpleNamespace(model="cx/wire-model", _key="test-secret", _base_url="https://test.invalid/v1",
                               _model_for_payload=lambda: "wire-model")
    router = SimpleNamespace(llm=lambda mode: provider)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await audit.check("cx-gateway", router, client, asyncio.Semaphore(1))
    assert result["status"] == expected
    assert "test-secret" not in capsys.readouterr().out
    assert ("firstTextMs" in result) == (expected == "responding")
