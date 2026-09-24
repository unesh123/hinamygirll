"""OmniRoute is wired as a *measured* local fallback, never as an unlimited brain.

The defect class these tests pin is the one this deployment has already been
burned by twice: a gateway keeps its environment variables after its container
stops, so a health check that only reads config manufactures a green badge for a
brain that cannot answer a single turn. Every claim below therefore goes through
either a real socket or an explicitly faked probe result.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from hinaa_api.circuit_breaker import reset_circuit_breakers
from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.main import create_app
from hinaa_api.reachability import GatewayModelsOutcome, probe_gateway_models, reset_models_cache
from hinaa_api.services import ConversationService, ProviderRouter

BLANKS = {
    "HINAA_PROVIDER_MODE": "mock",
    "AZURE_SPEECH_KEY": "",
    "AZURE_SPEECH_REGION": "",
    "GEMINI_API_KEY": "",
    "GROQ_API_KEY": "",
    "OPENAI_API_KEY": "",
    "OPENAI_CODEX_API_KEY": "",
    "OPENAI_CODEX_BASE_URL": "",
    "AGENT_ROUTER_API_KEY": "",
    "AGENT_ROUTER_BASE_URL": "",
    "CX_GATEWAY_API_KEY": "",
    "CX_GATEWAY_BASE_URL": "",
    "ELEVENLABS_API_KEY": "",
    "HINAA_DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "HINAA_AUTH_MODE": "dev",
    "HINAA_PERSISTENCE_ENABLED": False,
    "HINAA_AGENT_RUNTIME_ENABLED": False,
    "HINAA_VMC_PORT": 0,
}


def omniroute_settings(**overrides) -> Settings:
    return Settings(**{**BLANKS, **overrides, "_env_file": None})


BASE_SETTINGS = omniroute_settings()
ENABLED = {"HINAA_OMNIROUTE_ENABLED": True}


@dataclass
class ServedGateway:
    """A stand-in for the OmniRoute container: it answers /v1/models or it does not."""

    url: str
    paths: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    bodies: list[dict] = field(default_factory=list)


@dataclass
class GatewayFactory:
    servers: list[ThreadingHTTPServer] = field(default_factory=list)

    def start(
        self,
        *,
        status: int = 200,
        body: bytes = b'{"data":[]}',
        completion: str | None = None,
    ) -> ServedGateway:
        served: ServedGateway = ServedGateway(url="")

        class Handler(BaseHTTPRequestHandler):
            def _send(self, status: int, payload: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self) -> None:  # noqa: N802 - http.server naming
                served.paths.append(self.path)
                served.methods.append("GET")
                self._send(status, body)

            def do_POST(self) -> None:  # noqa: N802 - http.server naming
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                served.paths.append(self.path)
                served.methods.append("POST")
                try:
                    request = json.loads(raw)
                except ValueError:
                    request = {}
                served.bodies.append(request)
                text = completion if completion is not None else ""
                if request.get("stream"):
                    # A gateway answers a stream request with SSE. Returning a
                    # plain object here is indistinguishable from a gateway that
                    # speaks no streaming at all, which would fail the turn.
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    chunk = {
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": text},
                                "finish_reason": "stop",
                            }
                        ]
                    }
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                else:
                    self._send(
                        200,
                        json.dumps(
                            {"choices": [{"message": {"role": "assistant", "content": text}}]}
                        ).encode(),
                    )

            def log_message(self, *_args) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.servers.append(server)
        served.url = f"http://127.0.0.1:{server.server_address[1]}/v1"
        return served

    def stop_all(self) -> None:
        for server in self.servers:
            server.shutdown()
            server.server_close()


@pytest.fixture(autouse=True)
def _clear_probe_caches():
    reset_models_cache()
    yield
    reset_models_cache()


@pytest.fixture
def gateway():
    factory = GatewayFactory()
    try:
        yield factory.start
    finally:
        factory.stop_all()


def _closed_port_url() -> str:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return f"http://127.0.0.1:{port}/v1"


class TestGatewayModelsProbe:
    def test_a_serving_gateway_reports_its_model_count(self, gateway) -> None:
        served = gateway(body=b'{"data":[{"id":"auto"},{"id":"gpt-4o"}]}')

        outcome = asyncio.run(probe_gateway_models(served.url, use_cache=False))

        assert (outcome.serving, outcome.model_count, outcome.reason) == (True, 2, "ok")
        assert served.paths == ["/v1/models"]

    def test_a_bare_host_still_probes_the_openai_models_route(self, gateway) -> None:
        served = gateway()

        asyncio.run(probe_gateway_models(served.url.removesuffix("/v1"), use_cache=False))

        assert served.paths == ["/v1/models"]

    def test_a_dead_port_is_not_serving(self) -> None:
        outcome = asyncio.run(probe_gateway_models(_closed_port_url(), use_cache=False))

        # This machine takes ~2s to report a refused loopback connection, so a
        # 1.5s budget usually sees the timeout rather than the refusal. Both are
        # connect-level proofs that nothing is serving, and neither may be
        # reported as a gateway that is up.
        assert outcome.serving is False
        assert outcome.reason in {"refused", "timeout"}
        assert outcome.model_count == 0

    def test_a_non_200_is_not_serving(self, gateway) -> None:
        served = gateway(status=404, body=b'{"error":"no route"}')

        outcome = asyncio.run(probe_gateway_models(served.url, use_cache=False))

        assert outcome.serving is False
        assert outcome.reason == "http_404"

    def test_a_200_without_a_model_list_is_not_serving(self, gateway) -> None:
        served = gateway(body=b'{"health":"ok"}')

        outcome = asyncio.run(probe_gateway_models(served.url, use_cache=False))

        assert outcome.serving is False
        assert outcome.reason == "malformed"

    def test_a_bare_list_response_still_counts(self, gateway) -> None:
        served = gateway(body=b'[{"id":"auto"}]')

        outcome = asyncio.run(probe_gateway_models(served.url, use_cache=False))

        assert (outcome.serving, outcome.model_count) == (True, 1)

    @pytest.mark.parametrize("candidate", [None, "", "   "])
    def test_no_url_never_claims_a_gateway(self, candidate) -> None:
        outcome = asyncio.run(probe_gateway_models(candidate, use_cache=False))

        assert outcome.serving is False
        assert outcome.reason == "no_url"

    def test_results_are_cached_so_polling_does_not_reconnect(self, gateway) -> None:
        served = gateway(body=b'{"data":[{"id":"auto"}]}')

        asyncio.run(probe_gateway_models(served.url))
        asyncio.run(probe_gateway_models(served.url))

        assert served.paths == ["/v1/models"]


class TestOmniRouteSettings:
    def test_disabled_by_default(self) -> None:
        assert BASE_SETTINGS.omniroute_enabled is False
        assert BASE_SETTINGS.omniroute_configured is False

    def test_declared_only_when_enabled_and_local(self) -> None:
        settings = omniroute_settings(**ENABLED, OMNIROUTE_BASE_URL="http://127.0.0.1:20128/v1")

        assert settings.omniroute_configured is True

    def test_a_remote_gateway_is_refused(self) -> None:
        settings = omniroute_settings(
            **ENABLED, OMNIROUTE_BASE_URL="https://somebody-elses-proxy.example/v1"
        )

        assert settings.omniroute_enabled is True
        assert settings.omniroute_is_local is False
        assert settings.omniroute_configured is False

    def test_the_api_suffix_is_added_exactly_once(self) -> None:
        assert (
            omniroute_settings(OMNIROUTE_BASE_URL="http://127.0.0.1:20128").active_omniroute_base_url
            == "http://127.0.0.1:20128/v1"
        )
        assert (
            omniroute_settings(
                OMNIROUTE_BASE_URL="http://localhost:20128/v1/"
            ).active_omniroute_base_url
            == "http://localhost:20128/v1"
        )

    def test_no_key_means_no_bearer_header(self) -> None:
        assert BASE_SETTINGS.active_omniroute_key == ""


class TestProviderRouter:
    def test_unconfigured_gateway_raises_an_actionable_error(self) -> None:
        router = ProviderRouter(BASE_SETTINGS)

        with pytest.raises(HinaaError) as raised:
            router.llm("omniroute")

        assert raised.value.code == "PROVIDER_CONFIGURATION_MISSING"
        assert "HINAA_OMNIROUTE_ENABLED" in raised.value.message

    def test_declared_gateway_resolves_to_its_own_provider_identity(self) -> None:
        router = ProviderRouter(
            omniroute_settings(**ENABLED, OMNIROUTE_BASE_URL="http://127.0.0.1:20128/v1")
        )

        provider = router.llm("omniroute")

        assert provider.id == "omniroute"
        assert provider._model == "auto"
        assert provider._base_url == "http://127.0.0.1:20128/v1"


class _LadderHost:
    """Exercise the ladder without constructing a whole conversation service."""

    _fallback_candidate_modes = ConversationService._fallback_candidate_modes

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def modes(self, primary: str) -> list[str]:
        return [mode for mode, _ in asyncio.run(self._fallback_candidate_modes(primary))]


def _fake_probe(monkeypatch, *, serving: bool) -> None:
    async def probe(*_args, **_kwargs):
        return GatewayModelsOutcome(
            serving,
            3 if serving else 0,
            "ok" if serving else "refused",
            "serving" if serving else "not answering",
        )

    monkeypatch.setattr("hinaa_api.services.probe_gateway_models", probe)


class TestFallbackLadder:
    def test_absent_when_not_declared(self, monkeypatch) -> None:
        _fake_probe(monkeypatch, serving=True)

        assert "omniroute" not in _LadderHost(BASE_SETTINGS).modes("claude")

    def test_absent_when_declared_but_not_answering(self, monkeypatch) -> None:
        _fake_probe(monkeypatch, serving=False)
        host = _LadderHost(omniroute_settings(**ENABLED))

        assert "omniroute" not in host.modes("claude")

    def test_a_serving_gateway_joins_the_ladder_last(self, monkeypatch) -> None:
        _fake_probe(monkeypatch, serving=True)
        host = _LadderHost(omniroute_settings(**ENABLED, GEMINI_API_KEY="test-gemini-key"))

        modes = host.modes("claude")

        assert modes[-1] == "omniroute", "the paid brains must be tried before the gateway"
        assert "real" in modes
        assert modes.index("real") < modes.index("omniroute")

    def test_the_gateway_is_not_offered_to_itself(self, monkeypatch) -> None:
        _fake_probe(monkeypatch, serving=True)
        host = _LadderHost(omniroute_settings(**ENABLED, GEMINI_API_KEY="test-gemini-key"))

        assert "omniroute" not in host.modes("omniroute")


class TestCapabilitiesReporting:
    def _payload(self, settings: Settings) -> dict:
        with TestClient(create_app(settings)) as client:
            return client.get("/api/v1/capabilities").json()

    @staticmethod
    def _entry(payload: dict) -> dict:
        return next(provider for provider in payload["providers"] if provider["id"] == "omniroute")

    def test_reports_not_configured_while_the_container_is_down(self) -> None:
        payload = self._payload(
            omniroute_settings(**ENABLED, OMNIROUTE_BASE_URL=_closed_port_url())
        )

        entry = self._entry(payload)
        assert entry["declared"] is True
        assert entry["configured"] is False
        assert entry["role"] == "fallback"
        assert entry["allowedModels"] == []

    def test_reports_configured_only_once_the_gateway_answers(self, gateway) -> None:
        served = gateway(body=b'{"data":[{"id":"auto"},{"id":"deepseek-chat"},{"id":"kimi-k3"}]}')

        entry = self._entry(
            self._payload(omniroute_settings(**ENABLED, OMNIROUTE_BASE_URL=served.url))
        )

        assert entry["configured"] is True
        assert entry["servingModels"] == 3

    def test_its_auto_selector_is_never_offered_as_a_pickable_brain(self, gateway) -> None:
        served = gateway(body=b'{"data":[{"id":"auto"}]}')

        payload = self._payload(omniroute_settings(**ENABLED, OMNIROUTE_BASE_URL=served.url))

        assert "auto" not in {model["id"] for model in payload["models"]}


class TestProviderStatusReporting:
    def _entry(self, settings: Settings) -> dict:
        with TestClient(create_app(settings)) as client:
            response = client.get("/api/v1/providers")
            assert response.status_code == 200
            return next(entry for entry in response.json() if entry["id"] == "omniroute")

    def test_disabled_reports_disabled_rather_than_broken(self) -> None:
        entry = self._entry(BASE_SETTINGS)

        assert entry["state"] == "disabled"
        assert "HINAA_OMNIROUTE_ENABLED" in entry["userMessage"]

    def test_enabled_but_dead_reports_unavailable_with_the_measured_reason(self) -> None:
        entry = self._entry(
            omniroute_settings(**ENABLED, OMNIROUTE_BASE_URL=_closed_port_url())
        )

        assert entry["state"] == "unavailable"
        assert "not answering" in entry["userMessage"]

    def test_a_live_gateway_reports_healthy_and_says_it_is_a_fallback(self, gateway) -> None:
        served = gateway(body=b'{"data":[{"id":"auto"},{"id":"gpt-4o"}]}')

        entry = self._entry(omniroute_settings(**ENABLED, OMNIROUTE_BASE_URL=served.url))

        assert entry["state"] == "healthy"
        assert "2 models" in entry["userMessage"]
        assert "fallback" in entry["userMessage"]
        assert "fallback-only" in entry["capabilities"]

    def test_a_remote_url_is_refused_with_an_explanation(self) -> None:
        entry = self._entry(
            omniroute_settings(**ENABLED, OMNIROUTE_BASE_URL="https://elsewhere.example/v1")
        )

        assert entry["state"] == "unavailable"
        assert "loopback" in entry["userMessage"]


def _turn(settings: Settings, provider_mode: str) -> list[dict]:
    """Stream one real turn through the running app and return its NDJSON events."""
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/conversations/turns:stream",
            json={
                "sessionId": "omniroute-e2e",
                "text": "I need you. Tell me you love me and finish your sentence.",
                "companionId": "hinaa",
                "language": "mixed",
                "providerMode": provider_mode,
            },
        )
    assert response.status_code == 200
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def _plan(events: list[dict]) -> dict:
    return next(event["plan"] for event in events if event.get("type") == "plan")


class TestTurnLandsOnTheGateway:
    """A fallback that has never answered a turn is theatre, so this goes through
    the real request path: a primary brain whose endpoint is a closed port fails
    with a genuine connection error, the live ladder demotes it, and the reply
    crosses a real socket into an OpenAI-compatible server.
    """

    DEAD_PRIMARY = {"CX_GATEWAY_API_KEY": "test-cx-key"}

    @pytest.fixture(autouse=True)
    def _fresh_breakers(self):
        # The dead primary is a real failure, so it records on the shared
        # breaker. Without this, the cooldown leaks into unrelated files.
        reset_circuit_breakers()
        yield
        reset_circuit_breakers()

    def _settings(self, gateway_url: str | None) -> Settings:
        return omniroute_settings(
            **ENABLED,
            **self.DEAD_PRIMARY,
            OMNIROUTE_BASE_URL=gateway_url or _closed_port_url(),
            CX_GATEWAY_BASE_URL=_closed_port_url(),
        )

    def test_a_failed_primary_turn_is_answered_by_the_gateway(self, gateway) -> None:
        served = gateway(
            body=b'{"data":[{"id":"auto"}]}',
            completion="I love you. That is the whole sentence, not a fragment.",
        )

        plan = _plan(_turn(self._settings(served.url), "cx-gateway"))

        assert plan["resolvedProvider"] == "omniroute"
        assert plan["fallback"] is True
        assert "cx-gateway" in (plan["fallbackReason"] or "")
        assert "I love you" in plan["displayText"]
        assert "/v1/models" in served.paths, "the ladder must gate on a live probe"
        assert "/v1/chat/completions" in served.paths, "the turn must reach completions"

    def test_the_gateway_is_asked_in_its_own_dialect(self, gateway) -> None:
        served = gateway(body=b'{"data":[{"id":"auto"}]}', completion="Here, still.")

        _turn(self._settings(served.url), "cx-gateway")

        request = served.bodies[-1]
        # OpenAI-only fields are the trap: `response_format` is a 400 on several
        # aggregators and an ignored `max_completion_tokens` silently removes the
        # output budget, which is how a reply starts getting cut mid-sentence.
        assert "response_format" not in request
        assert "max_completion_tokens" not in request
        assert request.get("max_tokens"), "no budget means a clipped spoken reply"
        assert request.get("model") == "auto", "the gateway's own selector must be honoured"

    def test_a_gateway_that_is_not_answering_is_not_blamed_for_the_turn(self) -> None:
        events = _turn(self._settings(None), "cx-gateway")

        # Both brains are dead, so the honest outcome is a typed failure naming
        # the real cause, never a plan attributed to a gateway that never replied.
        plans = [event["plan"] for event in events if event.get("type") == "plan"]
        assert [plan for plan in plans if plan.get("resolvedProvider") == "omniroute"] == []
        error = next(event for event in events if event.get("type") == "error")
        assert error["code"] == "PROVIDER_UNAVAILABLE"
