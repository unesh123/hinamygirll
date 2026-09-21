"""The public API must not let a stranger use HINAA to touch the host machine."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.tools import policy

TUNNEL_HOST = "try-hina.cf-teams.com"


def test_loopback_names_are_the_host_machine():
    assert policy.is_loopback_host("127.0.0.1:8000")
    assert policy.is_loopback_host("localhost:8000")
    assert policy.is_loopback_host("[::1]:8000")
    assert policy.is_loopback_host("LocalHost")


def test_tunnel_and_public_names_are_not_the_host_machine():
    assert not policy.is_loopback_host(TUNNEL_HOST)
    assert not policy.is_loopback_host(f"{TUNNEL_HOST}:443")
    assert not policy.is_loopback_host("hinaa-workspace.vercel.app")
    assert not policy.is_loopback_host(None)
    assert not policy.is_loopback_host("")


def test_local_effect_denied_over_tunnel_allowed_locally():
    settings = Settings(_env_file=None)
    denied = policy.decide("clipboard_get", settings, TUNNEL_HOST)
    assert denied.permitted is False
    assert denied.code == "LOCAL_TOOL_NOT_PERMITTED"
    assert policy.decide("clipboard_get", settings, "127.0.0.1:8000").permitted is True


def test_escape_hatch_opens_local_effects_over_tunnel():
    settings = Settings(HINAA_ALLOW_REMOTE_LOCAL_TOOLS=True, _env_file=None)
    assert policy.decide("clipboard_get", settings, TUNNEL_HOST).permitted is True


def test_irreversible_external_tool_needs_the_host_machine():
    settings = Settings(_env_file=None)
    verdict = policy.decide("send_email", settings, TUNNEL_HOST)
    assert verdict.permitted is False
    assert verdict.code == "IRREVERSIBLE_TOOL_NOT_PERMITTED"
    # The escape hatch is scoped to machine-touching tools; it does not re-open
    # actions that cannot be unsaid.
    override = Settings(HINAA_ALLOW_REMOTE_LOCAL_TOOLS=True, _env_file=None)
    assert policy.decide("send_email", override, TUNNEL_HOST).permitted is False


def test_informational_tools_are_unaffected():
    settings = Settings(_env_file=None)
    for name in ("web_search", "image_search", "image_generate", "deep_research", "pdf_generate"):
        assert policy.decide(name, settings, TUNNEL_HOST).permitted is True, name


def test_enforce_reads_the_bound_host_from_context():
    settings = Settings(_env_file=None)
    token = policy.set_request_host(TUNNEL_HOST)
    try:
        with pytest.raises(HinaaError) as caught:
            policy.enforce("screenshot", settings)
        assert caught.value.status_code == 403
        assert caught.value.code == "LOCAL_TOOL_NOT_PERMITTED"
    finally:
        policy.reset_request_host(token)

    token = policy.set_request_host("127.0.0.1:8000")
    try:
        policy.enforce("screenshot", settings)
    finally:
        policy.reset_request_host(token)


def _execute(client: TestClient, tool_name: str, host: str) -> tuple[int, dict]:
    response = client.post(
        "/api/v1/tools/execute",
        json={
            "toolName": tool_name,
            "parameters": {},
            # The pre-fix exploit: approval is asserted by the caller, so a
            # stranger can claim it.
            "confirmed": True,
            "approvalSource": "user",
        },
        headers={"host": host},
    )
    return response.status_code, response.json()


def test_execute_endpoint_denies_local_tool_from_public_origin(client: TestClient):
    status, body = _execute(client, "clipboard_get", TUNNEL_HOST)
    assert status == 403
    assert body["code"] == "LOCAL_TOOL_NOT_PERMITTED"


def test_execute_endpoint_permits_local_tool_on_the_host(client: TestClient):
    status, body = _execute(client, "system_info", "127.0.0.1:8000")
    assert body.get("code") != "LOCAL_TOOL_NOT_PERMITTED", body
    assert status != 403, body


def test_execute_endpoint_leaves_chat_tools_open(client: TestClient):
    status, body = _execute(client, "web_search", TUNNEL_HOST)
    assert body.get("code") not in {"LOCAL_TOOL_NOT_PERMITTED", "IRREVERSIBLE_TOOL_NOT_PERMITTED"}, body
    assert status != 403, body


@pytest.mark.asyncio
async def test_planned_agent_step_meets_the_same_rule(client: TestClient):
    """A chat turn that plans clipboard_get must not be a way around the gate."""
    from hinaa_api.agent.contracts import OperationType, PlanStep

    executor = client.app.state.agent_runtime.executor
    step = PlanStep(
        plan_id="plan_policy_probe",
        sequence=0,
        title="Read the clipboard",
        operation_type=OperationType.TOOL,
        tool_name="clipboard_get",
    )
    token = policy.set_request_host(TUNNEL_HOST)
    try:
        with pytest.raises(HinaaError) as caught:
            await executor(step)
    finally:
        policy.reset_request_host(token)
    assert caught.value.code == "LOCAL_TOOL_NOT_PERMITTED"
    assert caught.value.status_code == 403
