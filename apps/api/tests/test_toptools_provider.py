"""Targeted tests for Top-Tools AI gateway provider, capabilities, and HINAA_PRIMARY_BRAIN wiring."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from hinaa_api.brain_ledger import configured, fingerprint_for, record_call
from hinaa_api.capabilities import build_capability_registry
from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.main import create_app
from hinaa_api.providers.openai_llm import OpenAILLMProvider
from hinaa_api.services import ProviderRouter


def test_toptools_pinned_unsupported_model_does_not_silently_change():
    config = Settings(
        toptools_api_key=SecretStr("test-key"),
        toptools_allowed_models_raw="Top-Tools-Ai-Pro",
        toptools_model="Top-Tools-Ai-Pro",
        _env_file=None,
    )
    with pytest.raises(HinaaError) as error:
        ProviderRouter(config).llm("toptools", brain_model="unsupported-model")
    assert error.value.code == "PROVIDER_MODEL_NOT_ALLOWED"


@pytest.mark.parametrize(
    "changes",
    [
        {"toptools_api_key": SecretStr("new-key")},
        {"toptools_base_url": "https://another.example/v1"},
        {"toptools_model": "Top-Tools-Ai-Max"},
    ],
)
def test_toptools_health_evidence_is_scoped_to_connection(changes):
    config = Settings(toptools_api_key=SecretStr("original-key"), _env_file=None)
    fingerprint = fingerprint_for(config, "toptools")
    assert fingerprint
    assert fingerprint != fingerprint_for(config.model_copy(update=changes), "toptools")


def test_toptools_config_resolution():
    settings = Settings(
        toptools_api_key=SecretStr("sk-toptools-test-12345"),
        toptools_base_url="https://top-tools-ai.com/api/v1",
        toptools_model="Top-Tools-Ai-Pro",
        toptools_allowed_models_raw="Top-Tools-Ai-Pro,Top-Tools-Ai-Basic,Top-Tools-Ai-Max,*",
        primary_brain="toptools",
        _env_file=None,
    )
    assert settings.toptools_configured is True
    assert configured(settings, "toptools") is True
    assert settings.active_toptools_key is not None
    assert settings.active_toptools_key.get_secret_value() == "sk-toptools-test-12345"
    assert settings.active_toptools_base_url == "https://top-tools-ai.com/api/v1"
    assert settings.active_toptools_model == "Top-Tools-Ai-Pro"
    assert settings.resolve_toptools_model("Top-Tools-Ai-Basic") == "Top-Tools-Ai-Basic"

    primary_mode, reason = settings.resolve_primary_brain()
    assert primary_mode == "toptools"
    assert "selected" in reason


def test_toptools_missing_key_falls_back_to_xkiro():
    settings = Settings(
        toptools_api_key=None,
        primary_brain="toptools",
        _env_file=None,
    )
    assert settings.toptools_configured is False
    primary_mode, reason = settings.resolve_primary_brain()
    assert primary_mode == "xkiro"
    assert "not configured" in reason


def test_toptools_llm_provider_instantiation():
    settings = Settings(
        toptools_api_key=SecretStr("sk-toptools-test-12345"),
        toptools_base_url="https://top-tools-ai.com/api/v1",
        toptools_model="Top-Tools-Ai-Pro",
        primary_brain="toptools",
        _env_file=None,
    )
    router = ProviderRouter(settings)
    provider = router.llm(mode="toptools")
    assert isinstance(provider, OpenAILLMProvider)
    assert provider.model == "Top-Tools-Ai-Pro"
    assert provider.id == "toptools"


def test_toptools_capability_registry_reflection():
    settings = Settings(
        toptools_api_key=SecretStr("sk-toptools-test-12345"),
        toptools_base_url="https://top-tools-ai.com/api/v1",
        toptools_model="Top-Tools-Ai-Pro",
        primary_brain="toptools",
        _env_file=None,
    )
    registry = build_capability_registry(settings)
    assert registry.default_brain == "Top-Tools-Ai-Pro"
    assert "Primary brain toptools selected" in registry.primary_brain_reason
    toptools_models = {m.id: m for m in registry.models if m.provider == "toptools"}
    assert {"Top-Tools-Ai-Pro", "Top-Tools-Ai-Basic", "Top-Tools-Ai-Max"} <= set(toptools_models)
    assert toptools_models["Top-Tools-Ai-Pro"].availability == "healthy"


def test_toptools_capabilities_and_providers_endpoints(monkeypatch):
    from hinaa_api.reachability import GatewayModelsOutcome

    monkeypatch.setattr(
        "hinaa_api.main.probe_gateway_models",
        AsyncMock(return_value=GatewayModelsOutcome(True, 3, "ok", "Top-Tools AI catalog answered")),
    )
    settings = Settings(
        environment="development",
        auth_mode="dev",
        toptools_api_key=SecretStr("sk-toptools-test-12345"),
        toptools_base_url="https://top-tools-ai.com/api/v1",
        toptools_model="Top-Tools-Ai-Pro",
        toptools_allowed_models_raw="Top-Tools-Ai-Pro,Top-Tools-Ai-Basic,Top-Tools-Ai-Max,*",
        visible_providers_raw="coarena,toptools,local",
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        caps = client.get("/api/capabilities")
        assert caps.status_code == 200
        payload = caps.json()
        provider_map = {p["id"]: p for p in payload["providers"]}
        assert "toptools" in provider_map
        assert provider_map["toptools"]["name"] == "Top-Tools AI"
        assert provider_map["toptools"]["configured"] is True
        assert provider_map["toptools"]["defaultModel"] == "Top-Tools-Ai-Pro"

        model_ids = {m["id"] for m in payload["models"] if m["provider"] == "toptools"}
        assert {"Top-Tools-Ai-Pro", "Top-Tools-Ai-Basic", "Top-Tools-Ai-Max"} <= model_ids

        statuses = {p["id"]: p for p in client.get("/v1/providers").json()}
        assert "toptools" in statuses
        assert "default-model:Top-Tools-Ai-Pro" in statuses["toptools"]["capabilities"]
        assert "model:Top-Tools-Ai-Basic" in statuses["toptools"]["capabilities"]
        assert "model:Top-Tools-Ai-Max" in statuses["toptools"]["capabilities"]
        assert statuses["toptools"]["state"] == "untested"

        record_call(
            "toptools",
            ok=True,
            model="Top-Tools-Ai-Pro",
            fingerprint=fingerprint_for(settings, "toptools"),
        )
        statuses_after = {p["id"]: p for p in client.get("/v1/providers").json()}
        assert statuses_after["toptools"]["state"] == "healthy"


async def test_toptools_403_model_access_denied_does_not_lock_provider_key(monkeypatch):
    import httpx
    from hinaa_api.brain_ledger import newest_verdict
    from hinaa_api.circuit_breaker import get_circuit_breaker, reset_circuit_breakers

    reset_circuit_breakers()
    settings = Settings(
        toptools_api_key=SecretStr("sk-toptools-test-12345"),
        toptools_base_url="https://top-tools-ai.com/api/v1",
        toptools_model="Top-Tools-Ai-Pro",
        toptools_allowed_models_raw="Top-Tools-Ai-Pro,Top-Tools-Ai-Max",
        _env_file=None,
    )
    provider = ProviderRouter(settings).llm("toptools", brain_model="Top-Tools-Ai-Max")
    fp = fingerprint_for(settings, "toptools")
    record_call("toptools", ok=True, model="Top-Tools-Ai-Pro", fingerprint=fp)

    body = (
        b'{"error":{"message":"\\"Top-Tools-Ai-Max\\" is the Max plan\'s model. '
        b'Your model is \\"Top-Tools-Ai-Pro\\".","type":"permission_denied","code":"model_access_denied"}}'
    )
    resp = httpx.Response(403, content=body, request=httpx.Request("POST", "https://top-tools-ai.com/api/v1/chat/completions"))

    with pytest.raises(HinaaError) as exc:
        provider._raise_for_status(resp)
    assert exc.value.code == "PROVIDER_MODEL_NOT_ALLOWED"
    assert exc.value.status_code == 403
    assert get_circuit_breaker("toptools").can_execute()[0] is True

    record_call("toptools", ok=False, code=exc.value.code, detail=exc.value.message, fingerprint=fp)
    verdict = newest_verdict(["toptools"], fingerprints={"toptools": fp})
    assert verdict is not None
    assert verdict.state == "healthy"
    assert verdict.model == "Top-Tools-Ai-Pro"


async def test_toptools_stream_retries_once_on_keepalive_timeout(monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager

    settings = Settings(
        toptools_api_key=SecretStr("sk-toptools-test-12345"),
        toptools_base_url="https://top-tools-ai.com/api/v1",
        toptools_model="Top-Tools-Ai-Pro",
        _env_file=None,
    )
    provider = ProviderRouter(settings).llm("toptools")
    attempts = {"count": 0}

    class _FakeResp:
        status_code = 200
        headers = {}

        async def aiter_lines(self):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise TimeoutError("simulated keepalive stall")
            yield 'data: {"choices":[{"delta":{"content":"Recovered from Top-Tools AI"}}]}'
            yield "data: [DONE]"

    class _FakeClient:
        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            yield _FakeResp()

    @asynccontextmanager
    async def _fake_pool():
        yield _FakeClient()

    async def _fast_sleep(_):
        return None

    monkeypatch.setattr("hinaa_api.providers.openai_llm._pooled_client", _fake_pool)
    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)

    chunks = []
    async for ch in provider._stream_text("hi"):
        chunks.append(ch)
    assert attempts["count"] == 2
    assert "".join(chunks) == "Recovered from Top-Tools AI"
