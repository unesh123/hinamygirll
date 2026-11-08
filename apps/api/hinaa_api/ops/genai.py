"""GenAI spans + Prometheus metrics for LLM requests, agent turns and tool calls.

Span shapes follow the OpenTelemetry GenAI semantic conventions:
https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/client-inference.md
https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/execute-tool.md
Prompt/response content is opt-in (HINAA_OTEL_CAPTURE_CONTENT) and never recorded otherwise.
Metrics are always recorded; spans only when tracing is enabled.
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from . import metrics
from .otel import capture_content_enabled, get_tracer, tracing_enabled

PROVIDER_ANTHROPIC = "anthropic"
_MAX_CONTENT_CHARS = 32_000


def _dumps(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)[:_MAX_CONTENT_CHARS]


def _error_type(exc: BaseException) -> str:
    return type(exc).__qualname__


@contextmanager
def _span(name: str, kind_name: str, attributes: dict[str, Any]) -> Iterator[Any]:
    """Yield a started current span, or None when tracing is off."""
    if not tracing_enabled():
        yield None
        return
    from opentelemetry.trace import SpanKind, Status, StatusCode

    with get_tracer().start_as_current_span(
        name,
        kind=getattr(SpanKind, kind_name),
        attributes=attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except BaseException as exc:
            span.set_attribute("error.type", _error_type(exc))
            span.set_status(Status(StatusCode.ERROR, _error_type(exc)))
            raise


class LLMCall:
    def __init__(self, span: Any) -> None:
        self.span = span
        self.input_tokens = 0
        self.output_tokens = 0
        self.response_model: str | None = None

    def set_input(self, messages: Any, system: Any = None) -> None:
        if self.span is not None and capture_content_enabled():
            self.span.set_attribute("gen_ai.input.messages", _dumps(messages))
            if system:
                self.span.set_attribute("gen_ai.system_instructions", _dumps(system))

    def record_anthropic_response(self, data: dict[str, Any]) -> None:
        usage = data.get("usage") or {}
        cache_read = int(usage.get("cache_read_input_tokens") or 0)
        cache_write = int(usage.get("cache_creation_input_tokens") or 0)
        # Semconv input_tokens includes cached tokens; Anthropic reports them separately.
        self.input_tokens = int(usage.get("input_tokens") or 0) + cache_read + cache_write
        self.output_tokens = int(usage.get("output_tokens") or 0)
        self.response_model = data.get("model")
        span = self.span
        if span is None:
            return
        if self.response_model:
            span.set_attribute("gen_ai.response.model", self.response_model)
        if data.get("id"):
            span.set_attribute("gen_ai.response.id", str(data["id"]))
        span.set_attribute("gen_ai.usage.input_tokens", self.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", self.output_tokens)
        if cache_read:
            span.set_attribute("gen_ai.usage.cache_read.input_tokens", cache_read)
        if cache_write:
            span.set_attribute("gen_ai.usage.cache_write.input_tokens", cache_write)
        if data.get("stop_reason"):
            span.set_attribute("gen_ai.response.finish_reasons", [str(data["stop_reason"])])
        if capture_content_enabled():
            span.set_attribute("gen_ai.output.messages", _dumps(data.get("content")))


@contextmanager
def llm_call(
    *, provider: str, model: str | None, operation: str = "chat", max_tokens: int | None = None
) -> Iterator[LLMCall]:
    model_label = model or "unknown"
    attrs: dict[str, Any] = {
        "gen_ai.operation.name": operation,
        "gen_ai.provider.name": provider,
        "gen_ai.system": provider,
    }
    if model:
        attrs["gen_ai.request.model"] = model
    if max_tokens:
        attrs["gen_ai.request.max_tokens"] = int(max_tokens)
    start = time.perf_counter()
    outcome = "ok"
    with _span(f"{operation} {model}" if model else operation, "CLIENT", attrs) as span:
        call = LLMCall(span)
        try:
            yield call
        except BaseException:
            outcome = "error"
            raise
        finally:
            elapsed = time.perf_counter() - start
            metrics.LLM_REQUESTS.labels(provider, model_label, outcome).inc()
            metrics.LLM_LATENCY.labels(provider, model_label).observe(elapsed)
            resp_model = call.response_model or model_label
            if call.input_tokens:
                metrics.LLM_TOKENS.labels(provider, resp_model, "input").inc(call.input_tokens)
            if call.output_tokens:
                metrics.LLM_TOKENS.labels(provider, resp_model, "output").inc(call.output_tokens)


@contextmanager
def agent_turn(*, agent_name: str, provider: str, model: str | None) -> Iterator[Any]:
    attrs = {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.provider.name": provider,
        "gen_ai.agent.name": agent_name,
    }
    if model:
        attrs["gen_ai.request.model"] = model
    with _span(f"invoke_agent {agent_name}", "INTERNAL", attrs) as span:
        yield span


def _tool_label(name: str) -> str:
    """Bound metric cardinality: names the model invented collapse to 'unknown'."""
    from ..tools.registry import registry

    return name if registry.get_tool(name) is not None else "unknown"


class ToolCall:
    def __init__(self, span: Any) -> None:
        self.span = span
        self.outcome = "ok"

    def set_outcome(self, outcome: str) -> None:
        self.outcome = outcome

    def set_result(self, result: Any) -> None:
        if self.span is not None and capture_content_enabled():
            self.span.set_attribute("gen_ai.tool.call.result", _dumps(result))


@contextmanager
def tool_call(*, name: str, call_id: str | None = None, arguments: Any = None) -> Iterator[ToolCall]:
    attrs: dict[str, Any] = {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": name,
        "gen_ai.tool.type": "function",
    }
    if call_id:
        attrs["gen_ai.tool.call.id"] = call_id
    if arguments is not None and capture_content_enabled():
        attrs["gen_ai.tool.call.arguments"] = _dumps(arguments)
    start = time.perf_counter()
    with _span(f"execute_tool {name}", "INTERNAL", attrs) as span:
        call = ToolCall(span)
        try:
            yield call
        except BaseException:
            call.outcome = "error"
            raise
        finally:
            elapsed = time.perf_counter() - start
            if span is not None:
                span.set_attribute("hinaa.tool.outcome", call.outcome)
                span.set_attribute("hinaa.tool.duration_ms", round(elapsed * 1000, 2))
                if call.outcome == "error" and "error.type" not in (span.attributes or {}):
                    span.set_attribute("error.type", "tool_error")
            label = _tool_label(name)
            metrics.TOOL_CALLS.labels(label, call.outcome).inc()
            metrics.TOOL_LATENCY.labels(label).observe(elapsed)
