import json
from typing import Any

import httpx
import pytest

from hinaa_api.config import Settings
from hinaa_api.providers.anthropic_direct import AnthropicDirectProvider
from hinaa_api.providers.claude_brain import (
    PENDING_CONFIRMATION,
    ClaudeBrain,
    build_thinking_params,
    build_tool_schemas,
    messages_from_history,
    registry_executor,
    route_turn,
    visible_text,
)
from hinaa_api.tools.registry import ToolDefinition, ToolRegistry


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "HINAA_CLAUDE_API_KEY": "test-claude-key",
        "HINAA_DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "HINAA_AUTH_MODE": "dev",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


class FakeAnthropic:
    """httpx mock transport replaying scripted Messages API responses."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []
        self.payloads: list[dict[str, Any]] = []
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.payloads.append(json.loads(request.content))
        return httpx.Response(200, json=self.responses.pop(0))


def _message(content: list[dict[str, Any]], stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "type": "message",
        "role": "assistant",
        "content": content,
        "stop_reason": stop_reason,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def _tool_use(tool_id: str, name: str, **args: Any) -> dict[str, Any]:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": args}


def _thinking(text: str, signature: str) -> dict[str, Any]:
    return {"type": "thinking", "thinking": text, "signature": signature}


def _tool_registry(calls: list[tuple[str, dict[str, Any]]]) -> ToolRegistry:
    reg = ToolRegistry()

    def define(name: str, **kwargs: Any) -> None:
        async def handler(params: dict[str, Any]) -> dict[str, Any]:
            calls.append((name, dict(params)))
            return {"ok": True, "tool": name}

        reg.register(
            ToolDefinition(
                name=name,
                display_name=name.title(),
                description=f"{name} tool",
                parameters={"query": {"type": "string", "description": "q"}},
                required_parameters=["query"],
                **kwargs,
            ),
            handler,
        )

    define("web_search", is_read_only=True)
    define("file_read", is_read_only=True)
    define("send_email", requires_confirmation=True, risk_level="high")
    return reg


# --- configuration -----------------------------------------------------------


def test_model_defaults_and_backward_compatible_override() -> None:
    settings = _settings()
    assert settings.claude_tier_model("default") == "claude-sonnet-5-5"
    assert settings.claude_tier_model("deep") == "claude-opus-5-5"
    assert settings.claude_tier_model("fast") == "claude-haiku-5-5"

    legacy = _settings(HINAA_CLAUDE_MODEL="claude-sonnet-4-6")
    assert legacy.active_claude_model == "claude-sonnet-4-6"
    assert legacy.claude_tier_model("deep") == "claude-opus-5-5"

    custom = _settings(HINAA_CLAUDE_MODEL_DEEP="my-deep", HINAA_CLAUDE_MODEL_FAST="my-fast")
    assert custom.claude_tier_model("deep") == "my-deep"


def test_claude_is_preferred_when_keyed_unless_mode_is_explicit() -> None:
    assert _settings().provider_mode == "claude"
    assert _settings(HINAA_PROVIDER_MODE="mock").provider_mode == "mock"
    assert _settings(HINAA_CLAUDE_PREFER_WHEN_KEYED=False).provider_mode != "claude"
    assert _settings(HINAA_CLAUDE_API_KEY=None).provider_mode != "claude"


# --- routing -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "tier", "thinking"),
    [
        ("hey", "fast", False),
        ("thanks, that was great", "fast", False),
        (
            "What's a good name for a cat that likes naps and sunshine in the afternoon?",
            "default",
            False,
        ),
        ("Build me a website for my bakery with a landing page and contact form", "deep", True),
        ("Refactor this function:\n```python\ndef f(x):\n    return x\n```", "deep", True),
        ("Plan out a step-by-step roadmap for launching my app", "deep", True),
    ],
)
def test_routing_decisions(text: str, tier: str, thinking: bool) -> None:
    route = route_turn(text, _settings())
    assert (route.tier, route.thinking) == (tier, thinking)
    assert route.model == _settings().claude_tier_model(tier)


def test_voice_short_turn_uses_fast_and_attachments_never_do() -> None:
    settings = _settings()
    assert (
        route_turn("tell me about your day, how was it going so far", settings, is_voice=True).tier
        == "fast"
    )
    assert route_turn("hi", settings, has_attachments=True).tier == "default"
    assert route_turn("hi", settings, model_override="pinned").model == "pinned"


def test_thinking_params_adaptive_vs_manual() -> None:
    settings = _settings(
        HINAA_CLAUDE_THINKING_EFFORT="xhigh", HINAA_CLAUDE_THINKING_BUDGET_TOKENS=4000
    )
    fragment, max_tokens = build_thinking_params("claude-opus-5-5", settings, 2048)
    assert fragment == {"thinking": {"type": "adaptive"}, "output_config": {"effort": "xhigh"}}
    assert max_tokens == 2048

    fragment, max_tokens = build_thinking_params("claude-sonnet-4-20250514", settings, 2048)
    assert fragment == {"thinking": {"type": "enabled", "budget_tokens": 4000}}
    assert max_tokens > 4000
    assert (
        build_thinking_params("claude-opus-4-6", settings, 2048)[0]["thinking"]["type"]
        == "adaptive"
    )


# --- request shape -----------------------------------------------------------


@pytest.mark.asyncio
async def test_request_shape_headers_thinking_tools_and_cache_control() -> None:
    settings = _settings()
    fake = FakeAnthropic([_message([_thinking("hmm", "sig"), {"type": "text", "text": "Done."}])])
    reg = _tool_registry([])
    tools = build_tool_schemas(reg.get_all_tools(), settings)
    route = route_turn("Build me a website for my shop", settings)

    result = await ClaudeBrain(settings, fake.client).run(
        messages_from_history("Build me a website for my shop"),
        route=route,
        system="You are Hina.",
        tools=tools,
    )

    request, payload = fake.requests[0], fake.payloads[0]
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == "test-claude-key"
    assert request.headers["anthropic-version"] == settings.claude_api_version
    assert payload["model"] == "claude-opus-5-5"
    assert payload["thinking"] == {"type": "adaptive"}
    assert payload["output_config"] == {"effort": "high"}
    assert payload["system"] == [
        {"type": "text", "text": "You are Hina.", "cache_control": {"type": "ephemeral"}}
    ]
    assert [t["name"] for t in payload["tools"]] == ["web_search", "file_read", "send_email"]
    assert payload["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in payload["tools"][0]
    assert payload["tools"][0]["input_schema"] == {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "q"}},
        "required": ["query"],
    }
    # Thinking never leaks into the answer.
    assert result.text == "Done."
    assert "hmm" not in visible_text(result.messages[-1]["content"])


@pytest.mark.asyncio
async def test_fast_route_sends_no_thinking_and_one_hour_cache_ttl() -> None:
    settings = _settings(HINAA_CLAUDE_PROMPT_CACHE_TTL="1h")
    fake = FakeAnthropic([_message([{"type": "text", "text": "hi!"}])])
    result = await ClaudeBrain(settings, fake.client).run(
        messages_from_history("hey"), route=route_turn("hey", settings), system="sys"
    )
    payload = fake.payloads[0]
    assert payload["model"] == "claude-haiku-5-5"
    assert "thinking" not in payload and "output_config" not in payload and "tools" not in payload
    assert payload["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert result.text == "hi!"


# --- tool loop ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_loop_two_calls_then_answer_preserves_thinking_blocks() -> None:
    settings = _settings()
    calls: list[tuple[str, dict[str, Any]]] = []
    reg = _tool_registry(calls)
    first = [_thinking("need search", "sig-1"), _tool_use("tu_1", "web_search", query="cats")]
    second = [_thinking("now read", "sig-2"), _tool_use("tu_2", "file_read", query="notes.txt")]
    final = [{"type": "text", "text": "All set."}]
    fake = FakeAnthropic(
        [_message(first, "tool_use"), _message(second, "tool_use"), _message(final)]
    )

    result = await ClaudeBrain(settings, fake.client).run(
        messages_from_history("Research cats and plan out a roadmap"),
        route=route_turn("Research cats and plan out a roadmap", settings),
        tools=build_tool_schemas(reg.get_all_tools(), settings),
        executor=registry_executor(settings, registry=reg, host_header="localhost"),
    )

    assert result.text == "All set."
    assert result.steps == 3 and result.stop_reason == "end_turn"
    assert calls == [("web_search", {"query": "cats"}), ("file_read", {"query": "notes.txt"})]
    assert [e.status for e in result.tool_events] == ["ok", "ok"]

    third_messages = fake.payloads[2]["messages"]
    assert [m["role"] for m in third_messages] == ["user", "assistant", "user", "assistant", "user"]
    # Assistant turns, thinking + signature included, are replayed verbatim.
    assert third_messages[1]["content"] == first
    assert third_messages[3]["content"] == second
    tool_result = third_messages[4]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "tu_2"
    assert json.loads(tool_result["content"]) == {"ok": True, "tool": "file_read"}
    assert result.usage["input_tokens"] == 30


@pytest.mark.asyncio
async def test_max_steps_caps_the_loop() -> None:
    settings = _settings(HINAA_CLAUDE_TOOL_MAX_STEPS=2)
    calls: list[tuple[str, dict[str, Any]]] = []
    reg = _tool_registry(calls)
    looping = [
        _message([_tool_use(f"tu_{i}", "web_search", query="x")], "tool_use") for i in range(5)
    ]
    fake = FakeAnthropic(looping)

    result = await ClaudeBrain(settings, fake.client).run(
        messages_from_history("hello there"),
        route=route_turn("hello there", settings),
        tools=build_tool_schemas(reg.get_all_tools(), settings),
        executor=registry_executor(settings, registry=reg, host_header="localhost"),
    )

    assert result.max_steps_reached is True
    assert result.steps == 2 and len(fake.requests) == 2
    assert len(calls) == 1  # the capped call's tool_use is not executed


@pytest.mark.asyncio
async def test_confirmation_required_tool_is_not_executed() -> None:
    settings = _settings()
    calls: list[tuple[str, dict[str, Any]]] = []
    reg = _tool_registry(calls)
    fake = FakeAnthropic(
        [
            _message([_tool_use("tu_1", "send_email", query="to bob")], "tool_use"),
            _message([{"type": "text", "text": "Please confirm sending the email."}]),
        ]
    )

    result = await ClaudeBrain(settings, fake.client).run(
        messages_from_history("email bob"),
        route=route_turn("email bob", settings),
        tools=build_tool_schemas(reg.get_all_tools(), settings),
        executor=registry_executor(settings, registry=reg, host_header="localhost"),
    )

    assert calls == []
    assert [e.status for e in result.tool_events] == [PENDING_CONFIRMATION]
    assert result.pending_confirmations[0].tool == "send_email"
    sent = fake.payloads[1]["messages"][-1]["content"][0]
    assert json.loads(sent["content"])["status"] == PENDING_CONFIRMATION
    assert "is_error" not in sent
    assert result.text == "Please confirm sending the email."


@pytest.mark.asyncio
async def test_user_approved_executor_runs_confirmation_tool_and_unknown_tool_errors() -> None:
    settings = _settings()
    calls: list[tuple[str, dict[str, Any]]] = []
    reg = _tool_registry(calls)
    execute = registry_executor(settings, registry=reg, host_header="localhost", user_approved=True)
    assert (await execute("send_email", {"query": "hi"}))["ok"] is True
    assert "Unknown tool" in (await execute("nope", {}))["error"]
    assert "Missing required" in (await execute("web_search", {}))["error"]


@pytest.mark.asyncio
async def test_tool_exception_becomes_error_result_not_a_crash() -> None:
    settings = _settings()
    reg = _tool_registry([])
    fake = FakeAnthropic(
        [
            _message([_tool_use("tu_1", "web_search", query="x")], "tool_use"),
            _message([{"type": "text", "text": "Sorry, that failed."}]),
        ]
    )

    async def boom(name: str, params: dict[str, Any]) -> Any:
        raise RuntimeError("network down")

    result = await ClaudeBrain(settings, fake.client).run(
        messages_from_history("hi"),
        route=route_turn("hi", settings),
        tools=build_tool_schemas(reg.get_all_tools(), settings),
        executor=boom,
    )
    sent = fake.payloads[1]["messages"][-1]["content"][0]
    assert sent["is_error"] is True and "network down" in sent["content"]
    assert result.tool_events[0].status == "error"


# --- fallback / legacy -------------------------------------------------------


@pytest.mark.asyncio
async def test_no_key_means_unavailable_and_raises() -> None:
    settings = _settings(HINAA_CLAUDE_API_KEY=None)
    brain = ClaudeBrain(settings)
    assert brain.available is False
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        await brain.run([{"role": "user", "content": "hi"}], route=route_turn("hi", settings))


@pytest.mark.asyncio
async def test_direct_provider_generate_uses_configured_default_model() -> None:
    settings = _settings(HINAA_CLAUDE_MODEL="claude-sonnet-4-6")
    fake = FakeAnthropic([_message([{"type": "text", "text": "pong"}])])
    result = await AnthropicDirectProvider(settings, fake.client).generate("ping", system="s")
    assert result.value == "pong" and result.provider == "anthropic-direct"
    assert fake.payloads[0]["model"] == "claude-sonnet-4-6"
    # A "claude-opus-5.5" string is no longer diverted to another gateway.
    fake = FakeAnthropic([_message([{"type": "text", "text": "ok"}])])
    await AnthropicDirectProvider(settings, fake.client).generate("ping", model="claude-opus-5.5")
    assert str(fake.requests[0].url).startswith("https://api.anthropic.com/v1/messages")
