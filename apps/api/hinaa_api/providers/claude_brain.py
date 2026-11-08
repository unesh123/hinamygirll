"""Claude brain: model routing, thinking, prompt caching and a native tool loop.

Talks to the Anthropic Messages API through ``AnthropicDirectProvider``. Tool
calls run through the same policy/confirmation gates as ``/v1/tools/execute``;
a tool that needs confirmation is never executed here, the model is told it is
pending. Thinking blocks are replayed verbatim across tool turns (the API
requires that) and never reach the user-facing text.

Docs: https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking
      https://platform.claude.com/docs/en/build-with-claude/prompt-caching
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Literal

import httpx

from ..config import Settings
from ..ops import genai
from .anthropic_direct import AnthropicDirectProvider
from .blocks import extract_text_from_canonical_blocks, normalize_anthropic_block
from .fabric import ModelRouter, TaskType

logger = logging.getLogger("hinaa.providers.claude_brain")

Tier = Literal["fast", "default", "deep"]
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[Any]]

PENDING_CONFIRMATION = "pending_confirmation"
_TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
_MAX_TOOL_RESULT_CHARS = 20_000

_DEEP_RE = re.compile(
    r"\b(web\s?site|landing\s+page|web\s?app|front-?end|back-?end|build\s+(?:me\s+)?(?:a|an|the)\b|"
    r"implement|refactor|debug|stack\s?trace|algorithm|architecture|step[- ]by[- ]step|multi-?step|"
    r"roadmap|plan\s+(?:out|for|a|the)\b|prove|derive|analy[sz]e|investigate|compare|research|"
    r"design\s+(?:a|an|the)\b|write\s+(?:a|an|the)\s+(?:script|program|function|app|component)|"
    r"code|coding|sql\s+query|regex)\b",
    re.IGNORECASE,
)
_CHITCHAT_RE = re.compile(
    r"^(?:hi+|hey+|hello+|yo|namaste|good\s+(?:morning|night|evening)|thanks?(?:\s+you)?|ok(?:ay)?|"
    r"cool|nice|lol|how\s+are\s+you|what'?s\s+up|bye|goodnight)\b",
    re.IGNORECASE,
)
_router = ModelRouter()

# Pre-adaptive models still take manual thinking; 4.7+ rejects type "enabled".
_MANUAL_THINKING_RE = re.compile(
    r"^claude-(?:3\b|(?:opus|sonnet)-4(?:-[0-5])?(?:-\d{8})?$|haiku-4-5)"
)


@dataclass(frozen=True, slots=True)
class ClaudeRoute:
    tier: Tier
    model: str
    thinking: bool
    reason: str


def route_turn(
    text: str,
    settings: Settings,
    *,
    is_voice: bool = False,
    has_attachments: bool = False,
    model_override: str | None = None,
) -> ClaudeRoute:
    """Pick fast/default/deep for one turn, reusing the fabric complexity scorer."""
    context = {"images": has_attachments} if has_attachments else {}
    words = len(text.split())
    complexity = _router.score_complexity(text, context)
    task = _router.classify_task(text, context)
    deep = (
        task is TaskType.HARD_PLANNING
        or bool(_DEEP_RE.search(text))
        or "```" in text
        or complexity >= 0.45
    )

    if model_override:
        tier: Tier = "deep" if deep else "default"
        return ClaudeRoute(tier, model_override, deep, "explicit-model")
    if deep:
        tier, reason = "deep", "hard-reasoning"
    elif not has_attachments and (
        bool(_CHITCHAT_RE.match(text.strip()))
        or (words <= 12 and complexity < 0.2)
        or (is_voice and words <= 25 and complexity < 0.3)
    ):
        tier, reason = "fast", "short-chitchat"
    else:
        tier, reason = "default", "standard"
    return ClaudeRoute(tier, settings.claude_tier_model(tier), tier == "deep", reason)


def build_thinking_params(
    model: str, settings: Settings, max_tokens: int
) -> tuple[dict[str, Any], int]:
    """Return (payload fragment, max_tokens) enabling thinking for ``model``."""
    if _MANUAL_THINKING_RE.match(model):
        budget = settings.claude_thinking_budget_tokens
        # budget_tokens must stay below max_tokens, and answer room must remain.
        max_tokens = max(max_tokens, budget + 1024)
        return {"thinking": {"type": "enabled", "budget_tokens": budget}}, max_tokens
    return (
        {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": settings.claude_thinking_effort},
        },
        max_tokens,
    )


def cache_control(settings: Settings) -> dict[str, str]:
    control = {"type": "ephemeral"}
    if settings.claude_prompt_cache_ttl == "1h":
        control["ttl"] = "1h"
    return control


def build_system_blocks(system: str | None, settings: Settings) -> list[dict[str, Any]]:
    if not system:
        return []
    return [{"type": "text", "text": system, "cache_control": cache_control(settings)}]


def build_tool_schemas(
    tool_defs: list[Any], settings: Settings | None = None
) -> list[dict[str, Any]]:
    """Map ToolDefinition objects to Anthropic tool schemas (cache breakpoint on the last)."""
    tools: list[dict[str, Any]] = []
    for tool in tool_defs:
        if not _TOOL_NAME_RE.match(tool.name):
            continue
        properties = {
            key: ({"type": "string", **spec} if "type" not in spec else dict(spec))
            for key, spec in (tool.parameters or {}).items()
        }
        for spec in properties.values():
            spec.pop("required", None)
        tools.append(
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": [r for r in (tool.required_parameters or []) if r in properties],
                },
            }
        )
    if tools and settings is not None:
        tools[-1]["cache_control"] = cache_control(settings)
    return tools


@dataclass(slots=True)
class ToolEvent:
    tool: str
    tool_use_id: str
    status: Literal["ok", "error", PENDING_CONFIRMATION]
    input: dict[str, Any]


@dataclass(slots=True)
class ClaudeBrainResult:
    text: str
    route: ClaudeRoute
    steps: int
    stop_reason: str | None
    tool_events: list[ToolEvent] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    max_steps_reached: bool = False
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def pending_confirmations(self) -> list[ToolEvent]:
        return [e for e in self.tool_events if e.status == PENDING_CONFIRMATION]


def visible_text(content: list[dict[str, Any]]) -> str:
    """User-facing text only: thinking/tool blocks are dropped via blocks.py."""
    blocks = [
        normalized
        for raw in content
        if (normalized := normalize_anthropic_block(SimpleNamespace(**raw))) is not None
    ]
    return extract_text_from_canonical_blocks(blocks)


def _stringify(result: Any) -> str:
    if isinstance(result, str):
        text = result
    else:
        try:
            text = json.dumps(result, default=str, ensure_ascii=False)
        except TypeError, ValueError:
            text = str(result)
    if len(text) > _MAX_TOOL_RESULT_CHARS:
        text = text[:_MAX_TOOL_RESULT_CHARS] + "…[truncated]"
    return text


class ClaudeBrain:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        executor: ToolExecutor | None = None,
    ) -> None:
        self.settings = settings
        self.transport = AnthropicDirectProvider(settings, client)
        self.executor = executor

    @property
    def available(self) -> bool:
        return bool(self.transport._get_api_key())

    def build_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        route: ClaudeRoute,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        max_tokens = max_tokens or int(self.settings.llm_max_output_tokens)
        payload: dict[str, Any] = {"model": route.model, "messages": messages}
        if route.thinking:
            fragment, max_tokens = build_thinking_params(route.model, self.settings, max_tokens)
            payload.update(fragment)
        payload["max_tokens"] = max_tokens
        system_blocks = build_system_blocks(system, self.settings)
        if system_blocks:
            payload["system"] = system_blocks
        if tools:
            payload["tools"] = tools
        return payload

    async def run(
        self, messages: list[dict[str, Any]], *, route: ClaudeRoute, **kwargs: Any
    ) -> ClaudeBrainResult:
        """Traced entry point: one ``invoke_agent`` span per turn."""
        with genai.agent_turn(
            agent_name="hina", provider=genai.PROVIDER_ANTHROPIC, model=route.model
        ):
            return await self._run(messages, route=route, **kwargs)

    async def _run(
        self,
        messages: list[dict[str, Any]],
        *,
        route: ClaudeRoute,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        executor: ToolExecutor | None = None,
        max_steps: int | None = None,
        max_tokens: int | None = None,
    ) -> ClaudeBrainResult:
        """Run the tool_use -> tool_result loop until end_turn; ``max_steps`` caps model calls."""
        if not self.available:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")
        executor = executor or self.executor
        cap = max_steps or self.settings.claude_tool_max_steps
        transcript = [dict(m) for m in messages]
        result = ClaudeBrainResult(text="", route=route, steps=0, stop_reason=None)
        collected_text: list[str] = []

        while True:
            payload = self.build_payload(
                transcript, route=route, system=system, tools=tools, max_tokens=max_tokens
            )
            data = await self.transport.create_message(payload)
            result.steps += 1
            for key, value in (data.get("usage") or {}).items():
                if isinstance(value, int):
                    result.usage[key] = result.usage.get(key, 0) + value
            content = data.get("content") or []
            result.stop_reason = data.get("stop_reason")
            # Verbatim replay keeps thinking/redacted_thinking signatures valid.
            transcript.append({"role": "assistant", "content": content})
            text = visible_text(content)
            if text:
                collected_text.append(text)

            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            if result.stop_reason == "pause_turn":
                if result.steps >= cap:
                    result.max_steps_reached = True
                    break
                continue
            if result.stop_reason != "tool_use" or not tool_uses:
                break
            if executor is None:
                break
            if result.steps >= cap:
                result.max_steps_reached = True
                break
            transcript.append(
                {"role": "user", "content": await self._run_tools(tool_uses, executor, result)}
            )

        result.messages = transcript
        # Only the final assistant turn is the answer; earlier text was narration.
        result.text = (collected_text[-1] if collected_text else "").strip()
        return result

    async def _run_tools(
        self, tool_uses: list[dict[str, Any]], executor: ToolExecutor, result: ClaudeBrainResult
    ) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for use in tool_uses:
            name = str(use.get("name", ""))
            params = use.get("input") if isinstance(use.get("input"), dict) else {}
            status: Literal["ok", "error", "pending_confirmation"] = "ok"
            with genai.tool_call(name=name, call_id=use.get("id"), arguments=params) as tcall:
                try:
                    outcome = await executor(name, dict(params))
                    if isinstance(outcome, dict):
                        if outcome.get("status") == PENDING_CONFIRMATION:
                            status = PENDING_CONFIRMATION
                        elif outcome.get("error"):
                            status = "error"
                except Exception as exc:  # a tool failure is data for the model, not a crash
                    logger.warning("tool %s failed: %s", name, type(exc).__name__)
                    outcome, status = {"error": f"{name} failed: {exc}"}, "error"
                tcall.set_outcome(status)
                tcall.set_result(outcome)
            result.tool_events.append(ToolEvent(name, str(use.get("id")), status, dict(params)))
            block: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": use.get("id"),
                "content": _stringify(outcome),
            }
            if status == "error":
                block["is_error"] = True
            blocks.append(block)
        return blocks


def ensure_tools_loaded() -> None:
    try:
        from ..tools import load_all_tools

        load_all_tools()
    except Exception:  # pragma: no cover - optional tool modules must not block chat
        logger.exception("tool module load failed")


def registry_tool_defs(allowed: set[str] | None = None) -> list[Any]:
    from ..tools.registry import registry

    ensure_tools_loaded()
    return [t for t in registry.get_all_tools() if allowed is None or t.name in allowed]


def registry_executor(
    settings: Settings,
    *,
    host_header: str | None = None,
    user_id: str | None = None,
    user_approved: bool = False,
    registry: Any | None = None,
) -> ToolExecutor:
    """Executor over the tool registry using the same gates as /v1/tools/execute."""
    from ..tools import policy
    from ..tools.registry import registry as default_registry

    reg = registry or default_registry

    async def execute(name: str, params: dict[str, Any]) -> Any:
        tool_def = reg.get_tool(name)
        handler = reg._handlers.get(name)
        if tool_def is None or handler is None:
            return {"error": f"Unknown tool: {name}"}
        verdict = policy.decide(name, settings, host_header)
        if not verdict.permitted:
            return {"error": verdict.code, "message": verdict.message}

        needs_approval = tool_def.requires_confirmation
        if name == "computer_operator":
            tier = policy.classify_computer_operator_action(str(params.get("action", "")), params)
            needs_approval = (
                needs_approval
                or not policy.check_action_tier_authorization(
                    tier,
                    confirmed=user_approved,
                    approval_source="user" if user_approved else "none",
                ).permitted
            )
        if needs_approval and not user_approved:
            return {
                "status": PENDING_CONFIRMATION,
                "tool": name,
                "message": (
                    f"{tool_def.display_name} was NOT executed. It needs the user's explicit "
                    "confirmation; ask them to approve it."
                ),
                "parameters": params,
            }

        missing = [p for p in tool_def.required_parameters if params.get(p) is None]
        if missing:
            return {"error": f"Missing required argument(s): {', '.join(missing)}"}
        params.pop("user_id", None)
        params["userId"] = user_id or params.get("userId")
        if params["userId"] is None:
            params.pop("userId")
        arg: Any = params
        hints = list(inspect.signature(handler).parameters.values())
        if hints:
            annotation = hints[0].annotation
            if inspect.isclass(annotation) and hasattr(annotation, "model_validate"):
                arg = annotation(**params)
        return await asyncio.wait_for(handler(arg), timeout=tool_def.timeout_seconds)

    return execute


def messages_from_history(
    text: str, history: tuple[tuple[str, str], ...] = ()
) -> list[dict[str, Any]]:
    """Alternating user/assistant messages ending with the new user turn."""
    messages: list[dict[str, Any]] = []
    for role, content in history:
        if role not in ("user", "assistant") or not str(content).strip():
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += f"\n\n{content}"
        else:
            messages.append({"role": role, "content": str(content)})
    if messages and messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": "Hello"})
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += f"\n\n{text}"
    else:
        messages.append({"role": "user", "content": text})
    return messages


async def run_claude_turn(
    settings: Settings,
    text: str,
    *,
    system: str | None = None,
    history: tuple[tuple[str, str], ...] = (),
    is_voice: bool = False,
    use_tools: bool = True,
    host_header: str | None = None,
    user_id: str | None = None,
    client: httpx.AsyncClient | None = None,
    model_override: str | None = None,
) -> ClaudeBrainResult:
    """Route one turn and run it with Hina's registered tools."""
    route = route_turn(text, settings, is_voice=is_voice, model_override=model_override)
    brain = ClaudeBrain(settings, client)
    tools = None
    executor = None
    # The fast tier is chit-chat; skipping tools keeps its tool schemas out of the prompt.
    if use_tools and route.tier != "fast":
        tools = build_tool_schemas(registry_tool_defs(), settings) or None
        executor = registry_executor(settings, host_header=host_header, user_id=user_id)
    return await brain.run(
        messages_from_history(text, history),
        route=route,
        system=system,
        tools=tools,
        executor=executor,
    )
