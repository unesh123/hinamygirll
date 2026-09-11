from __future__ import annotations

import asyncio
from pydantic import BaseModel

from hinaa_api.tools.registry import registry
from hinaa_api.tools.registry import ToolDefinition


class _FutureAnnotatedParams(BaseModel):
    query: str


class _RequiredParams(BaseModel):
    query: str


async def _future_annotated_handler(params: _FutureAnnotatedParams) -> dict[str, object]:
    # Accessing .query intentionally reproduces the prior raw-dict crash when
    # postponed annotations were not resolved by the shared dispatcher.
    return {"status": "success", "data": {"received": params.query}}


async def _terminal_error_handler(params: _FutureAnnotatedParams) -> dict[str, object]:
    return {
        "status": "error",
        "code": "COMFYUI_UNAVAILABLE",
        "error": f"Local renderer unavailable for {params.query}",
        "localOnly": True,
    }


def test_execute_tool_resolves_postponed_pydantic_annotation(client, monkeypatch) -> None:
    monkeypatch.setitem(registry._handlers, "youtube_playback_request", _future_annotated_handler)

    response = client.post(
        "/v1/tools/execute",
        json={
            "toolName": "youtube_playback_request",
            "parameters": {"query": "Heavenly Phonk"},
            "confirmed": True,
            "approvalSource": "user",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success", "data": {"received": "Heavenly Phonk"}}


def test_execute_tool_preserves_terminal_provider_error(client, monkeypatch) -> None:
    monkeypatch.setitem(registry._handlers, "image_generate", _terminal_error_handler)

    response = client.post(
        "/v1/tools/execute",
        json={
            "toolName": "image_generate",
            "parameters": {"query": "a local portrait", "prompt": "a local portrait"},
            "confirmed": True,
            "approvalSource": "user",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "error",
        "code": "COMFYUI_UNAVAILABLE",
        "error": "Local renderer unavailable for a local portrait",
        "localOnly": True,
    }


def test_confirmation_tool_rejects_standing_consent(client) -> None:
    response = client.post(
        "/v1/tools/execute",
        json={
            "toolName": "youtube_playback_request",
            "parameters": {"query": "Heavenly Phonk"},
            "confirmed": True,
            "approvalSource": "standing-consent",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "TOOL_CONFIRMATION_REQUIRED"


def test_execute_tool_uses_server_owner_not_client_user_id(client, monkeypatch) -> None:
    definition = ToolDefinition(
        name="_owner_probe",
        display_name="Owner probe",
        description="test",
        parameters={},
        required_parameters=[],
        risk_level="low",
    )

    async def owner_handler(params: dict[str, object]) -> dict[str, object]:
        return {"receivedUserId": params.get("userId")}

    monkeypatch.setitem(registry._tools, definition.name, definition)
    monkeypatch.setitem(registry._handlers, definition.name, owner_handler)
    response = client.post(
        "/v1/tools/execute",
        headers={"X-HINAA-Dev-User": "victim-subject"},
        json={
            "toolName": definition.name,
            "parameters": {"userId": "attacker-controlled"},
            "userId": "attacker-controlled",
        },
    )

    assert response.status_code == 200
    received = response.json()["data"]["data"]["receivedUserId"]
    assert received and received != "attacker-controlled"


def test_execute_tool_enforces_definition_timeout(client, monkeypatch) -> None:
    definition = ToolDefinition(
        name="_timeout_probe",
        display_name="Timeout probe",
        description="test",
        parameters={},
        required_parameters=[],
        timeout_seconds=0.001,
        risk_level="low",
    )

    async def slow_handler(_params: dict[str, object]) -> dict[str, object]:
        await asyncio.sleep(0.05)
        return {"ok": True}

    monkeypatch.setitem(registry._tools, definition.name, definition)
    monkeypatch.setitem(registry._handlers, definition.name, slow_handler)
    response = client.post("/v1/tools/execute", json={"toolName": definition.name})

    assert response.status_code == 504
    assert response.json()["code"] == "TOOL_TIMEOUT"


def test_execute_tool_reports_invalid_arguments(client, monkeypatch) -> None:
    definition = ToolDefinition(
        name="_validation_probe",
        display_name="Validation probe",
        description="test",
        parameters={"query": {"type": "string"}},
        required_parameters=["query"],
        risk_level="low",
    )

    async def validation_handler(params: _RequiredParams) -> dict[str, object]:
        return {"query": params.query}

    monkeypatch.setitem(registry._tools, definition.name, definition)
    monkeypatch.setitem(registry._handlers, definition.name, validation_handler)
    response = client.post("/v1/tools/execute", json={"toolName": definition.name, "parameters": {}})

    assert response.status_code == 422
    assert response.json()["code"] == "TOOL_ARGUMENTS_INVALID"


def test_execute_tool_does_not_accept_client_policy_engine_approval(client) -> None:
    response = client.post(
        "/v1/tools/execute",
        json={
            "toolName": "youtube_playback_request",
            "parameters": {"query": "Heavenly Phonk"},
            "confirmed": True,
            "approvalSource": "policy-engine",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "TOOL_CONFIRMATION_REQUIRED"
