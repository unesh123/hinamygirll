"""OpenTelemetry tracing, GenAI spans/metrics, Sentry scrubbing and health probes."""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from pydantic import SecretStr

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.ops import metrics, otel
from hinaa_api.ops.context import JsonFormatter, RequestContextFilter
from hinaa_api.ops.setup import init_sentry, scrub_sentry_event
from hinaa_api.providers.anthropic_direct import AnthropicDirectProvider
from hinaa_api.providers.claude_brain import ClaudeBrain, ClaudeRoute

SECRET_PROMPT = "my-very-private-prompt-text"
SECRET_REPLY = "private-model-reply-text"
ANTHROPIC_REPLY: dict[str, Any] = {
    "id": "msg_01",
    "model": "claude-sonnet-resolved",
    "stop_reason": "end_turn",
    "content": [{"type": "text", "text": SECRET_REPLY}],
    "usage": {"input_tokens": 11, "output_tokens": 7, "cache_read_input_tokens": 3},
}
TOOL_USE_REPLY: dict[str, Any] = {
    **ANTHROPIC_REPLY,
    "stop_reason": "tool_use",
    "content": [{"type": "tool_use", "id": "toolu_1", "name": "diagnostic_echo", "input": {"text": "hi"}}],
}


@pytest.fixture
def fake_network(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    """Replace the real transport (before instrumentation wraps it) and record requests."""
    seen: list[httpx.Request] = []
    replies = [TOOL_USE_REPLY, ANTHROPIC_REPLY]

    async def handle(self: httpx.AsyncHTTPTransport, request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/messages"):
            body = json.loads(request.content)
            has_tool_result = any(
                isinstance(m.get("content"), list) and any(b.get("type") == "tool_result" for b in m["content"])
                for m in body["messages"]
            )
            return httpx.Response(200, json=ANTHROPIC_REPLY if (has_tool_result or not body.get("tools")) else replies[0])
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handle)
    return seen


@pytest.fixture
def otel_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={"otel_enabled": True, "claude_api_key": SecretStr("test-key")}
    )


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def traced(
    otel_settings: Settings, exporter: InMemorySpanExporter, fake_network: list[httpx.Request]
) -> Iterator[TestClient]:
    app = create_app(otel_settings.model_copy(update={"otel_enabled": False}))
    assert otel.setup_tracing(app, otel_settings, span_exporter=exporter)
    yield TestClient(app)
    otel.shutdown_tracing()


def _brain(settings: Settings, executor: Any = None) -> ClaudeBrain:
    return ClaudeBrain(settings, executor=executor)


ROUTE = ClaudeRoute(tier="standard", model="claude-sonnet-req", thinking=False, reason="test")  # type: ignore[arg-type]


def _by_name(exporter: InMemorySpanExporter, prefix: str) -> list[Any]:
    return [s for s in exporter.get_finished_spans() if s.name.startswith(prefix)]


# --- request tracing ---------------------------------------------------------


def test_request_span_has_route_attrs_resource_and_trace_header(
    traced: TestClient, exporter: InMemorySpanExporter
) -> None:
    response = traced.get("/v1/ledger/turns")
    spans = [s for s in exporter.get_finished_spans() if s.kind == SpanKind.SERVER]
    assert spans, "no server span recorded"
    span = spans[0]
    assert span.attributes["http.route"] == "/v1/ledger/turns"
    assert span.attributes.get("http.request.method", span.attributes.get("http.method")) == "GET"
    assert span.resource.attributes["service.name"] == "hinaa-api"
    assert span.resource.attributes["service.version"]
    assert "deployment.environment.name" in span.resource.attributes
    assert response.headers["X-Trace-Id"] == format(span.context.trace_id, "032x")


def test_incoming_traceparent_continues_trace(traced: TestClient, exporter: InMemorySpanExporter) -> None:
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    response = traced.get(
        "/v1/ledger/turns", headers={"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"}
    )
    assert response.headers["X-Trace-Id"] == trace_id
    assert any(format(s.context.trace_id, "032x") == trace_id for s in exporter.get_finished_spans())


def test_health_probes_are_not_traced(traced: TestClient, exporter: InMemorySpanExporter) -> None:
    traced.get("/healthz")
    traced.get("/readyz")
    assert exporter.get_finished_spans() == ()


def test_json_logs_carry_trace_and_span_id(traced: TestClient) -> None:
    logger = logging.getLogger("hinaa.test")
    with otel.get_tracer().start_as_current_span("unit") as span:
        record = logger.makeRecord("hinaa.test", logging.INFO, __file__, 1, "hello", (), None)
        RequestContextFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
        ctx = span.get_span_context()
    assert payload["trace_id"] == format(ctx.trace_id, "032x")
    assert payload["span_id"] == format(ctx.span_id, "016x")


async def test_httpx_child_span_and_traceparent_propagation(
    traced: TestClient, exporter: InMemorySpanExporter, fake_network: list[httpx.Request]
) -> None:
    with otel.get_tracer().start_as_current_span("parent") as parent:
        async with httpx.AsyncClient() as client:
            await client.get("https://example.test/ping")
    parent_ctx = parent.get_span_context()
    client_spans = [s for s in exporter.get_finished_spans() if s.kind == SpanKind.CLIENT]
    assert len(client_spans) == 1
    assert client_spans[0].parent.span_id == parent_ctx.span_id
    sent = fake_network[-1].headers["traceparent"]
    assert sent.split("-")[1] == format(parent_ctx.trace_id, "032x")
    assert sent.split("-")[2] == format(client_spans[0].context.span_id, "016x")


# --- GenAI spans -------------------------------------------------------------


async def test_llm_span_follows_genai_conventions(
    traced: TestClient, exporter: InMemorySpanExporter, otel_settings: Settings
) -> None:
    provider = AnthropicDirectProvider(otel_settings)
    payload = {
        "model": "claude-sonnet-req",
        "max_tokens": 64,
        "messages": [{"role": "user", "content": SECRET_PROMPT}],
    }
    await provider.create_message(payload)

    (span,) = _by_name(exporter, "chat ")
    assert span.name == "chat claude-sonnet-req"
    assert span.kind == SpanKind.CLIENT
    attrs = span.attributes
    assert attrs["gen_ai.operation.name"] == "chat"
    assert attrs["gen_ai.provider.name"] == "anthropic"
    assert attrs["gen_ai.request.model"] == "claude-sonnet-req"
    assert attrs["gen_ai.response.model"] == "claude-sonnet-resolved"
    assert attrs["gen_ai.usage.input_tokens"] == 14  # 11 + 3 cache-read
    assert attrs["gen_ai.usage.output_tokens"] == 7
    assert attrs["gen_ai.usage.cache_read.input_tokens"] == 3
    assert tuple(attrs["gen_ai.response.finish_reasons"]) == ("end_turn",)
    http_spans = [s for s in exporter.get_finished_spans() if s.name == "POST"]
    assert http_spans and http_spans[0].parent.span_id == span.context.span_id


async def test_llm_error_marks_span_and_metrics(
    traced: TestClient, exporter: InMemorySpanExporter, otel_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(self: httpx.AsyncHTTPTransport, request: httpx.Request) -> httpx.Response:
        return httpx.Response(529, json={"error": "overloaded"}, request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", boom)
    before = metrics.LLM_REQUESTS.labels("anthropic", "err-model", "error")._value.get()
    with pytest.raises(httpx.HTTPStatusError):
        await AnthropicDirectProvider(otel_settings).create_message(
            {"model": "err-model", "max_tokens": 8, "messages": []}
        )
    (span,) = _by_name(exporter, "chat ")
    assert span.attributes["error.type"] == "HTTPStatusError"
    assert metrics.LLM_REQUESTS.labels("anthropic", "err-model", "error")._value.get() == before + 1


async def test_content_not_captured_by_default(
    traced: TestClient, exporter: InMemorySpanExporter, otel_settings: Settings
) -> None:
    result = await _brain(otel_settings, _echo_executor).run(
        [{"role": "user", "content": SECRET_PROMPT}], route=ROUTE, tools=[{"name": "diagnostic_echo"}]
    )
    assert result.text == SECRET_REPLY
    dumped = json.dumps([dict(s.attributes) for s in exporter.get_finished_spans()], default=str)
    assert SECRET_PROMPT not in dumped and SECRET_REPLY not in dumped
    assert "gen_ai.input.messages" not in dumped and "gen_ai.tool.call.arguments" not in dumped


async def test_content_captured_only_when_opted_in(
    otel_settings: Settings, exporter: InMemorySpanExporter, fake_network: list[httpx.Request]
) -> None:
    opted = otel_settings.model_copy(update={"otel_capture_content": True})
    app = create_app(opted.model_copy(update={"otel_enabled": False}))
    assert otel.setup_tracing(app, opted, span_exporter=exporter)
    try:
        await AnthropicDirectProvider(opted).create_message(
            {"model": "m", "max_tokens": 8, "messages": [{"role": "user", "content": SECRET_PROMPT}]}
        )
    finally:
        otel.shutdown_tracing()
    (span,) = _by_name(exporter, "chat ")
    assert SECRET_PROMPT in span.attributes["gen_ai.input.messages"]
    assert SECRET_REPLY in span.attributes["gen_ai.output.messages"]


async def _echo_executor(name: str, params: dict[str, Any]) -> Any:
    return {"echo": params}


async def test_tool_span_nests_under_agent_turn_and_llm_spans(
    traced: TestClient, exporter: InMemorySpanExporter, otel_settings: Settings
) -> None:
    before = metrics.TOOL_CALLS.labels("unknown", "ok")._value.get()
    await _brain(otel_settings, _echo_executor).run(
        [{"role": "user", "content": "hello"}], route=ROUTE, tools=[{"name": "diagnostic_echo"}]
    )
    (agent,) = _by_name(exporter, "invoke_agent")
    (tool,) = _by_name(exporter, "execute_tool")
    llm = _by_name(exporter, "chat ")
    assert agent.attributes["gen_ai.operation.name"] == "invoke_agent"
    assert tool.name == "execute_tool diagnostic_echo"
    assert tool.kind == SpanKind.INTERNAL
    assert tool.attributes["gen_ai.tool.name"] == "diagnostic_echo"
    assert tool.attributes["gen_ai.tool.call.id"] == "toolu_1"
    assert tool.attributes["hinaa.tool.outcome"] == "ok"
    assert tool.attributes["hinaa.tool.duration_ms"] >= 0
    assert tool.parent.span_id == agent.context.span_id
    assert len(llm) == 2 and all(s.parent.span_id == agent.context.span_id for s in llm)
    assert metrics.TOOL_CALLS.labels("diagnostic_echo", "ok")._value.get() >= 1 or (
        metrics.TOOL_CALLS.labels("unknown", "ok")._value.get() == before + 1
    )


async def test_tool_failure_is_recorded_as_error(
    traced: TestClient, exporter: InMemorySpanExporter, otel_settings: Settings
) -> None:
    async def failing(name: str, params: dict[str, Any]) -> Any:
        raise RuntimeError("nope")

    await _brain(otel_settings, failing).run(
        [{"role": "user", "content": "hello"}], route=ROUTE, tools=[{"name": "diagnostic_echo"}]
    )
    (tool,) = _by_name(exporter, "execute_tool")
    assert tool.attributes["hinaa.tool.outcome"] == "error"
    assert tool.attributes["error.type"] == "tool_error"


# --- disabled mode -----------------------------------------------------------


async def test_disabled_mode_creates_no_spans_but_keeps_metrics(
    settings: Settings, exporter: InMemorySpanExporter, fake_network: list[httpx.Request]
) -> None:
    otel.shutdown_tracing()
    off = settings.model_copy(update={"otel_enabled": False, "claude_api_key": SecretStr("k")})
    app = create_app(off)
    assert otel.setup_tracing(app, off, span_exporter=exporter) is False
    assert not otel.tracing_enabled() and otel.current_ids() is None
    before = metrics.LLM_REQUESTS.labels("anthropic", "off-model", "ok")._value.get()
    await AnthropicDirectProvider(off).create_message({"model": "off-model", "max_tokens": 8, "messages": []})
    response = TestClient(app).get("/v1/ledger/turns")
    assert exporter.get_finished_spans() == ()
    assert "traceparent" not in fake_network[0].headers
    assert len(response.headers["X-Trace-Id"]) == 32
    assert metrics.LLM_REQUESTS.labels("anthropic", "off-model", "ok")._value.get() == before + 1


def test_enabled_without_endpoint_is_skipped(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    on = settings.model_copy(update={"otel_enabled": True})
    assert otel.setup_tracing(create_app(settings), on) is False


# --- metrics -----------------------------------------------------------------


def test_metrics_endpoint_exposes_genai_series(settings: Settings) -> None:
    metrics.LLM_LATENCY.labels("anthropic", "expo-model").observe(0.3)
    metrics.LLM_TOKENS.labels("anthropic", "expo-model", "input").inc(5)
    metrics.TOOL_CALLS.labels("expo_tool", "ok").inc()
    body = TestClient(create_app(settings), client=("127.0.0.1", 50000)).get("/metrics").text
    assert 'hinaa_llm_request_duration_seconds_bucket{le="0.5",model="expo-model",provider="anthropic"}' in body
    assert 'hinaa_llm_tokens_total{model="expo-model",provider="anthropic",type="input"}' in body
    assert 'hinaa_tool_calls_total{outcome="ok",tool="expo_tool"}' in body


# --- Sentry ------------------------------------------------------------------


def test_sentry_scrubber_removes_credentials_and_pii() -> None:
    event = {
        "request": {
            "headers": {"Authorization": "Bearer abcdefghijklmnop", "X-Api-Key": "k", "Accept": "json"},
            "cookies": {"sid": "1"},
            "data": {"password": "x"},
            "url": "https://h/x?api_key=sk-abcdefghijklmnopqrstuv",
        },
        "user": {"id": "u1", "email": "a@b.c", "ip_address": "1.2.3.4"},
        "extra": {"anthropic_api_key": "sk-ant-abcdefghijklmnopqrstuvwx", "note": "ok Bearer zzzzzzzzzzzz"},
        "breadcrumbs": {"values": [{"data": {"cookie": "a=b"}}]},
    }
    out = scrub_sentry_event(event)
    dumped = json.dumps(out)
    assert out["request"]["headers"]["Authorization"] == "[Filtered]"
    assert out["request"]["headers"]["X-Api-Key"] == "[Filtered]"
    assert out["request"]["headers"]["Accept"] == "json"
    assert "cookies" not in out["request"] and "data" not in out["request"]
    assert out["user"] == {"id": "u1"}
    for leaked in ("abcdefghijklmnop", "sk-ant-", "zzzzzzzzzzzz", "a=b", "1.2.3.4", "a@b.c"):
        assert leaked not in dumped


def test_sentry_event_is_tagged_with_trace_id(traced: TestClient) -> None:
    with otel.get_tracer().start_as_current_span("err") as span:
        out = scrub_sentry_event({})
    assert out["tags"]["trace_id"] == format(span.get_span_context().trace_id, "032x")


def test_init_sentry_wires_scrubber(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    import sentry_sdk

    captured: dict[str, Any] = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: captured.update(kw))
    on = settings.model_copy(update={"sentry_dsn": SecretStr("https://k@o0.ingest.sentry.io/1")})
    assert init_sentry(on) is True
    assert captured["before_send"] is scrub_sentry_event
    assert captured["send_default_pii"] is False and captured["include_local_variables"] is False


# --- health ------------------------------------------------------------------


def test_healthz_is_cheap_liveness(settings: Settings) -> None:
    response = TestClient(create_app(settings)).get("/healthz")
    assert response.status_code == 200 and response.json()["status"] == "ok"
    assert "database" not in response.json()


def test_readyz_reports_database_and_migrations(settings: Settings, tmp_path: Any) -> None:
    on = settings.model_copy(
        update={
            "persistence_enabled": True,
            "database_url": f"sqlite+pysqlite:///{tmp_path / 'ready.db'}",
        }
    )
    client = TestClient(create_app(on))
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["database"]["ok"] is True
    assert response.json()["database"]["migrationsPending"] == []


def test_readyz_fails_on_pending_migration_or_dead_db(settings: Settings, tmp_path: Any) -> None:
    from sqlalchemy import text

    on = settings.model_copy(
        update={
            "persistence_enabled": True,
            "database_url": f"sqlite+pysqlite:///{tmp_path / 'pending.db'}",
        }
    )
    app = create_app(on)
    from hinaa_api.persistence.db import get_session_factory

    engine = get_session_factory(on).kw["bind"]
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM schema_migrations WHERE version = (SELECT MAX(version) FROM schema_migrations)"))
    response = TestClient(app).get("/readyz")
    assert response.status_code == 503
    assert response.json()["database"]["migrationsPending"]
    engine.dispose()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE schema_migrations"))
    assert TestClient(app).get("/readyz").status_code == 503
    assert TestClient(app).get("/healthz").status_code == 200
