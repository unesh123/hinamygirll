"""A brain's badge may only be as green as the last live call to it.

The defect this pins is the one measured in production: `/v1/providers` reported
Claude healthy with "no live call has been made" while every turn fell back to
another brain, because the badge was built from environment variables that
outlived the credential's HTTP 403. Every assertion below therefore compares the
reported state against either a call that really crossed a socket or an outcome
the turn path wrote, and the "untested" state is the honest gap in between.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from hinaa_api.brain_ledger import (
    LIVE_OUTCOME_WINDOW_SECONDS,
    fingerprints_for,
    ledger_path,
    newest_verdict,
    record_call,
    reset_ledger,
    row_for_brain,
)
from hinaa_api.circuit_breaker import reset_circuit_breakers
from hinaa_api.config import Settings
from hinaa_api.main import create_app

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


def brain_settings(**overrides) -> Settings:
    return Settings(**{**BLANKS, **overrides, "_env_file": None})


# A deployment that looks like the owner's: several paid brains configured, so
# one rejecting its credential must not be able to hide behind another's badge.
MULTI_BRAIN = brain_settings(
    HINAA_PROVIDER_MODE="claude",
    claude_api_key="claude-key-for-tests",
    codecraft_api_key="codecraft-key-for-tests",
    GEMINI_API_KEY="gemini-key-for-tests",
)


@dataclass
class StubGateway:
    """Stand-in for an OpenAI-compatible brain endpoint."""

    url: str
    paths: list[str] = field(default_factory=list)


@dataclass
class StubFactory:
    servers: list[ThreadingHTTPServer] = field(default_factory=list)

    def start(self, *, status: int = 200, completion: str = "Here, still.") -> StubGateway:
        served = StubGateway(url="")

        class Handler(BaseHTTPRequestHandler):
            def _send(self, code: int, payload: bytes) -> None:
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self) -> None:  # noqa: N802 - http.server naming
                served.paths.append(self.path)
                self._send(200, b'{"data":[{"id":"gpt-5.6-sol"}]}')

            def do_POST(self) -> None:  # noqa: N802 - http.server naming
                served.paths.append(self.path)
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if status >= 400:
                    self._send(status, json.dumps({"error": {"message": "forbidden"}}).encode())
                    return
                try:
                    wants_stream = bool(json.loads(raw).get("stream"))
                except ValueError:
                    wants_stream = False
                if wants_stream:
                    # A gateway answers a stream request with SSE; a plain object
                    # here is indistinguishable from a brain that said nothing.
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    chunk = {
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": completion},
                                "finish_reason": "stop",
                            }
                        ]
                    }
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    return
                self._send(
                    200,
                    json.dumps(
                        {"choices": [{"message": {"role": "assistant", "content": completion}}]}
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


@pytest.fixture
def stub():
    factory = StubFactory()
    try:
        yield factory.start
    finally:
        factory.stop_all()


@pytest.fixture(autouse=True)
def _fresh_breakers():
    reset_circuit_breakers()
    yield
    reset_circuit_breakers()


def _row(client: TestClient, row_id: str) -> dict:
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    return next(entry for entry in response.json() if entry["id"] == row_id)


def _capability(client: TestClient, row_id: str) -> dict:
    return next(
        entry
        for entry in client.get("/api/v1/capabilities").json()["providers"]
        if entry["id"] == row_id
    )


def _fingerprint(settings: Settings, row_id: str) -> str:
    return fingerprints_for(settings, row_id).get(row_id, "")


class TestUntestedIsNotHealthy:
    def test_a_configured_brain_is_untested_until_a_call_answers(self) -> None:
        with TestClient(create_app(MULTI_BRAIN)) as client:
            claude = _row(client, "claude")

        assert claude["state"] == "untested"
        assert "no live call" in claude["userMessage"].lower()
        assert "llm" in claude["capabilities"]

    def test_the_model_picker_reports_the_same_gap(self) -> None:
        # The composer chip reads /v1/capabilities, so both surfaces must agree
        # or one of them keeps lying somewhere.
        with TestClient(create_app(MULTI_BRAIN)) as client:
            entry = _capability(client, "claude")

        assert entry["configured"] is True, "the credential really is present"
        assert entry["health"] == "untested"
        assert "no live call" in entry["healthMessage"].lower()

    def test_in_process_brains_stay_reported_ready(self) -> None:
        # These answer from this process with no network, so configuration does
        # prove them and demoting them would be its own false alarm.
        with TestClient(create_app(MULTI_BRAIN)) as client:
            assert _row(client, "mock")["state"] == "healthy"
            assert _row(client, "local")["state"] in {"healthy", "degraded"}

    def test_a_row_no_brain_reports_to_is_not_pinned_untested(self) -> None:
        # `gemini-live` shares the Gemini credential and no provider ever names
        # itself that, so a ledger-only rule would leave it untested forever.
        with TestClient(create_app(MULTI_BRAIN)) as client:
            assert _row(client, "gemini-live")["state"] == "healthy"

    def test_a_brain_without_a_credential_is_reported_not_configured(self) -> None:
        # Measured on a deployment with no keys: the row says the variable is
        # missing, and an outcome carrying no credential identity cannot paint
        # over that, because "untested" and "healthy" both promise a call exists.
        record_call("groq", ok=True, model="llama-guard")

        with TestClient(create_app(MULTI_BRAIN)) as client:
            row = _row(client, "groq")
            entry = _capability(client, "groq")

        assert row["state"] == "unavailable"
        assert "not configured" in row["userMessage"].lower()
        assert entry["configured"] is False
        assert entry["health"] == "unavailable"
        assert "not configured" in entry["healthMessage"].lower()


class TestVerdictsFromOutcomes:
    def test_an_answered_call_earns_healthy(self) -> None:
        settings = MULTI_BRAIN
        record_call(
            "claude",
            ok=True,
            model="claude-sonnet-4-6",
            fingerprint=_fingerprint(settings, "claude"),
        )

        with TestClient(create_app(settings)) as client:
            claude = _row(client, "claude")

        assert claude["state"] == "healthy"
        assert "answered the last live call" in claude["userMessage"]
        assert "claude-sonnet-4-6" in claude["userMessage"]

    def test_a_rejected_key_is_reported_as_unavailable_with_the_cause(self) -> None:
        settings = MULTI_BRAIN
        record_call(
            "claude",
            ok=False,
            code="PROVIDER_KEY_INVALID",
            detail="Claude rejected this credential (HTTP 403). Check the key and its billing.",
            fingerprint=_fingerprint(settings, "claude"),
        )

        with TestClient(create_app(settings)) as client:
            claude = _row(client, "claude")

        assert claude["state"] == "unavailable"
        assert "403" in claude["userMessage"]

    def test_a_throttled_call_reads_as_degraded_not_dead(self) -> None:
        settings = MULTI_BRAIN
        record_call(
            "claude",
            ok=False,
            code="PROVIDER_RATE_LIMIT",
            detail="Claude is rate limited right now.",
            fingerprint=_fingerprint(settings, "claude"),
        )

        with TestClient(create_app(settings)) as client:
            assert _row(client, "claude")["state"] == "degraded"

    def test_one_brain_s_failure_does_not_colour_another(self) -> None:
        settings = MULTI_BRAIN
        record_call(
            "claude",
            ok=False,
            code="PROVIDER_KEY_INVALID",
            detail="rejected",
            fingerprint=_fingerprint(settings, "claude"),
        )

        with TestClient(create_app(settings)) as client:
            assert _row(client, "claude")["state"] == "unavailable"
            assert _row(client, "codecraft")["state"] == "untested"

    def test_a_call_named_by_its_client_lights_the_badge_it_answers_to(self) -> None:
        # One /v1/providers row can front several client implementations; the
        # evidence is recorded under the name that ran.
        settings = brain_settings(AGENT_ROUTER_API_KEY="router-key")
        record_call(
            "agent-router-openai",
            ok=True,
            model="agnes-2.5-flash",
            fingerprint=_fingerprint(settings, "agent-router"),
        )

        with TestClient(create_app(settings)) as client:
            entry = _row(client, "agent-router")

        assert row_for_brain("agent-router-openai") == "agent-router"
        assert entry["state"] == "healthy"
        assert "agnes-2.5-flash" in entry["userMessage"]

    def test_a_refusal_is_not_reported_as_an_infrastructure_failure(self) -> None:
        # Declining one prompt is an answer; it says nothing about the credential.
        record_call(
            "claude",
            ok=False,
            code="SAFETY_REFUSAL",
            detail="Claude declined to generate content due to safety policy.",
        )

        assert newest_verdict(["claude"]) is None

    def test_the_in_process_brains_never_write_the_ledger(self) -> None:
        record_call("mock-llm-v3", ok=True)
        record_call("local-zero-credit-llm-v1", ok=False, code="PROVIDER_UNAVAILABLE")

        assert ledger_path().exists() is False


class TestEvidenceDecay:
    def test_the_verdict_outlives_the_process_that_measured_it(self) -> None:
        # This backend is a bare uvicorn restarted by hand; a verdict that only
        # lived in memory would report everything as broken after each restart.
        settings = MULTI_BRAIN
        fingerprint = _fingerprint(settings, "claude")
        record_call("claude", ok=False, code="PROVIDER_KEY_INVALID", detail="403", fingerprint=fingerprint)

        reset_ledger()  # a restart keeps the file and drops the in-memory view

        with TestClient(create_app(settings)) as client:
            assert _row(client, "claude")["state"] == "unavailable"

    def test_a_replaced_credential_voids_the_old_verdict(self) -> None:
        # Failing a call made with a key the owner has since swapped would keep
        # a fixed brain red, because clients stop selecting it and never re-probe.
        broken = brain_settings(claude_api_key="claude-key-before")
        fixed = brain_settings(claude_api_key="claude-key-after")
        record_call(
            "claude",
            ok=False,
            code="PROVIDER_KEY_INVALID",
            detail="403",
            fingerprint=_fingerprint(broken, "claude"),
        )
        assert _fingerprint(broken, "claude") != _fingerprint(fixed, "claude")

        with TestClient(create_app(fixed)) as client:
            assert _row(client, "claude")["state"] == "untested"

    def test_stale_evidence_reports_as_untested_not_healthy(self) -> None:
        settings = MULTI_BRAIN
        record_call("claude", ok=True, fingerprint=_fingerprint(settings, "claude"))
        outcomes = json.loads(ledger_path().read_text(encoding="utf-8"))
        outcomes["claude"]["at"] -= LIVE_OUTCOME_WINDOW_SECONDS + 60
        ledger_path().write_text(json.dumps(outcomes), encoding="utf-8")
        reset_ledger()

        verdict = newest_verdict(["claude"])
        assert verdict is None

        with TestClient(create_app(settings)) as client:
            assert _row(client, "claude")["state"] == "untested"


class TestVerdictsComeFromRealTurns:
    """The recording sites live in the turn path, so these go through the running
    app and a real socket rather than calling the ledger directly."""

    def _settings(self, url: str) -> Settings:
        return brain_settings(
            HINAA_PROVIDER_MODE="cx-gateway",
            CX_GATEWAY_API_KEY="test-cx-key",
            CX_GATEWAY_BASE_URL=url,
        )

    def _turn(self, settings: Settings) -> tuple[list[dict], dict]:
        with TestClient(create_app(settings)) as client:
            response = client.post(
                "/v1/conversations/turns:stream",
                json={
                    "sessionId": "brain-ledger-e2e",
                    "text": "Tell me you love me and finish your sentence.",
                    "companionId": "hinaa",
                    "language": "mixed",
                    "providerMode": "cx-gateway",
                },
            )
            assert response.status_code == 200
            events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
            row = _row(client, "cx-gateway")
        return events, row

    def test_a_turn_the_gateway_rejected_is_the_badge(self, stub) -> None:
        # This is the exact production failure: HTTP 403 with the environment
        # still in place. Before the ledger the badge stayed green through it.
        served = stub(status=403)

        events, row = self._turn(self._settings(served.url))

        assert row["state"] == "unavailable"
        assert "403" in row["userMessage"]
        assert any(event.get("type") == "error" for event in events)

    def test_a_turn_answered_by_the_gateway_is_reported_live(self, stub) -> None:
        served = stub(completion="I love you. That is the whole sentence.")

        events, row = self._turn(self._settings(served.url))

        assert row["state"] == "healthy"
        assert "answered the last live call" in row["userMessage"]
        assert "/v1/chat/completions" in served.paths, "the badge must follow a completion, not a probe"
        plans = [event["plan"] for event in events if event.get("type") == "plan"]
        assert plans and plans[-1]["resolvedProvider"] == "cx-gateway"


class TestHealthNamesTheAnsweringBrain:
    """/health used to answer "which brain is configured?", and that stayed true
    for weeks in which a flash-tier gateway wrote every word. A status built this
    way has to come from a call that really happened.
    """

    def _health(self, settings: Settings) -> dict:
        with TestClient(create_app(settings)) as client:
            response = client.get("/health")
        assert response.status_code == 200, "readiness stays a configuration contract"
        return response.json()

    def test_the_brain_that_answered_is_named_when_it_is_not_the_one_asked(self) -> None:
        settings = MULTI_BRAIN
        record_call(
            "claude",
            ok=False,
            code="PROVIDER_KEY_INVALID",
            detail="Claude gateway rejected this credential (HTTP 403).",
            fingerprint=_fingerprint(settings, "claude"),
        )
        record_call("agent-router-openai", ok=True, model="agnes-2.5-flash")

        health = self._health(settings)

        assert health["mode"] == "claude", "what the owner asked for is still a fact"
        assert health["answeredBy"]["brain"] == "agent-router-openai"
        assert health["answeredBy"]["row"] == "agent-router"
        assert health["answeredBy"]["model"] == "agnes-2.5-flash"
        assert health["requestedServed"] is False
        assert health["fallback"] is True
        assert health["status"] == "degraded"
        assert "403" in health["routing"]
        assert "agent-router-openai" in health["routing"]

    def test_ok_requires_the_configured_brain_to_have_answered(self) -> None:
        settings = MULTI_BRAIN
        record_call(
            "claude",
            ok=True,
            model="claude-sonnet-4-6",
            fingerprint=_fingerprint(settings, "claude"),
        )

        health = self._health(settings)

        assert health["status"] == "ok"
        assert health["requestedServed"] is True
        assert health["fallback"] is False
        assert "answered the last live call" in health["routing"]
        assert "claude-sonnet-4-6" in health["routing"]

    def test_with_no_live_answer_the_claim_is_not_made(self) -> None:
        health = self._health(MULTI_BRAIN)

        assert health["answeredBy"] is None
        assert health["status"] == "degraded"
        assert "recently enough" in health["routing"]

    def test_a_missing_credential_is_reported_as_not_configured(self) -> None:
        # "untested" promises a call could have happened. With no key there is
        # nothing to have measured, and the endpoint has to say that out loud.
        health = self._health(brain_settings(HINAA_PROVIDER_MODE="claude"))

        assert health["status"] == "degraded"
        assert "not configured" in health["routing"]

    def test_an_in_process_brain_needs_no_socket_to_be_believed(self) -> None:
        health = self._health(brain_settings(HINAA_PROVIDER_MODE="mock"))

        assert health["status"] == "ok"
        assert "in-process" in health["routing"]

    def test_a_real_turn_is_what_changes_the_sentence(self, stub) -> None:
        # Written by the turn path and read back here, so neither half can be
        # asserted in isolation from the other.
        served = stub(completion="I love you. That is the whole sentence.")
        settings = brain_settings(
            HINAA_PROVIDER_MODE="cx-gateway",
            CX_GATEWAY_API_KEY="test-cx-key",
            CX_GATEWAY_BASE_URL=served.url,
        )

        with TestClient(create_app(settings)) as client:
            before = client.get("/health").json()
            response = client.post(
                "/v1/conversations/turns:stream",
                json={
                    "sessionId": "health-routing-e2e",
                    "text": "Tell me you love me and finish your sentence.",
                    "companionId": "hinaa",
                    "language": "mixed",
                    "providerMode": "cx-gateway",
                },
            )
            assert response.status_code == 200
            after = client.get("/health").json()

        assert before["answeredBy"] is None
        assert after["answeredBy"]["brain"] == "cx-gateway"
        assert after["requestedServed"] is True
        assert after["status"] == "ok"
        assert after["answeredBy"]["model"], "name the model that ran, not the one requested"

    def test_a_turn_that_died_before_its_plan_still_names_a_brain(self, stub) -> None:
        # The client learns the failure from the error event alone, and that event
        # used to carry no routing at all — so a rejected Claude request kept its
        # Claude badge on screen even though nothing had answered.
        served = stub(status=403)
        settings = brain_settings(
            HINAA_PROVIDER_MODE="cx-gateway",
            CX_GATEWAY_API_KEY="test-cx-key",
            CX_GATEWAY_BASE_URL=served.url,
        )

        with TestClient(create_app(settings)) as client:
            response = client.post(
                "/v1/conversations/turns:stream",
                json={
                    "sessionId": "health-error-routing",
                    "text": "Say something kind.",
                    "companionId": "hinaa",
                    "language": "mixed",
                    "providerMode": "cx-gateway",
                },
            )

        errors = [
            event for event in (json.loads(line) for line in response.text.splitlines() if line.strip())
            if event.get("type") == "error"
        ]
        assert errors, "the turn must report its failure"
        routing = errors[-1]["routing"]
        assert routing["answeredBy"] is None, "nothing answered, and the event must not imply otherwise"
        assert "403" in routing["reason"]
