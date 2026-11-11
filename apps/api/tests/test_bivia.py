import httpx
import pytest
from pydantic import SecretStr

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.providers.bivia import BiviaDecisionRequest, decide
from hinaa_api.tools.registry import registry


@pytest.mark.asyncio
async def test_bivia_request_validation():
    # Requires at least 2 outcomes
    with pytest.raises(Exception):
        BiviaDecisionRequest(state="context", question="what to do?", outcomes=["only_one"])

    # Requires distinct outcomes
    with pytest.raises(Exception):
        BiviaDecisionRequest(state="context", question="what to do?", outcomes=["a", "a"])

    valid = BiviaDecisionRequest(state="context", question="what to do?", outcomes=["opt1", "opt2"])
    assert valid.outcomes == ["opt1", "opt2"]
    assert valid.mode == "fast"


@pytest.mark.asyncio
async def test_bivia_not_configured():
    settings = Settings(articul8_api_key=None)
    req = BiviaDecisionRequest(state="context", question="what to do?", outcomes=["a", "b"])
    with pytest.raises(HinaaError) as exc_info:
        await decide(settings, req)
    assert exc_info.value.code == "BIVIA_NOT_CONFIGURED"
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_bivia_answered_decision():
    settings = Settings(articul8_api_key=SecretStr("mock-key"))
    req = BiviaDecisionRequest(state="context", question="which option?", outcomes=["optA", "optB"])

    async def mock_handler(request: httpx.Request):
        assert request.headers.get("apikey") == "mock-key"
        return httpx.Response(
            200,
            json={"status": "answered", "value": "optA", "probability": 0.95},
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        res = await decide(settings, req, client=client)

    assert res["status"] == "answered"
    assert res["value"] == "optA"
    assert res["probability"] == 0.95
    assert res["provider"] == "articul8"
    assert res["authorizesExecution"] is False


@pytest.mark.asyncio
async def test_bivia_auth_rejection():
    settings = Settings(articul8_api_key=SecretStr("bad-key"))
    req = BiviaDecisionRequest(state="context", question="which option?", outcomes=["optA", "optB"])

    transport = httpx.MockTransport(lambda req: httpx.Response(401, json={"error": "unauthorized"}))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(HinaaError) as exc_info:
            await decide(settings, req, client=client)

    assert exc_info.value.code == "BIVIA_AUTH_REJECTED"
    assert exc_info.value.status_code == 502
    assert exc_info.value.user_action_required is True


@pytest.mark.asyncio
async def test_bivia_abstained_decision():
    settings = Settings(articul8_api_key=SecretStr("mock-key"))
    req = BiviaDecisionRequest(state="ambiguous context", question="which option?", outcomes=["optA", "optB"])

    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json={"status": "abstained", "value": None, "abstain_reason": "Insufficient context to decide"},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        res = await decide(settings, req, client=client)

    assert res["status"] == "abstained"
    assert res["value"] is None
    assert "Insufficient" in res["abstain_reason"]


def test_bivia_tool_registered():
    tool = registry.get("bivia_decide")
    assert tool is not None
    assert tool.risk_level == "low"
    assert tool.is_read_only is True
