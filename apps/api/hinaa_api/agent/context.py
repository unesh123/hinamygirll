from __future__ import annotations

from typing import Any

from .contracts import TurnContext, TurnContextItem


def _estimate_tokens(content: str) -> int:
    return max(1, (len(content) + 3) // 4)


def _fit_text(content: str, token_budget: int) -> str:
    """Keep both ends of oversized input while enforcing the context budget."""
    max_chars = token_budget * 4
    if len(content) <= max_chars:
        return content
    marker = "\n...[truncated]...\n"
    remaining = max_chars - len(marker)
    head_size = remaining // 2
    tail_size = remaining - head_size
    return f"{content[:head_size]}{marker}{content[-tail_size:]}"


class ContextBuilder:
    def __init__(self, max_tokens: int = 4000) -> None:
        if max_tokens < 64:
            raise ValueError("max_tokens must be at least 64")
        self.max_tokens = max_tokens

    def build(
        self,
        current_message: str,
        *,
        recent_messages: list[dict[str, Any]] | None = None,
        summary: str | None = None,
        memories: list[dict[str, Any]] | None = None,
        project: dict[str, Any] | None = None,
        attachments: list[str] | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        user_id: str | None = None,
    ) -> TurnContext:
        bounded_current_message = _fit_text(current_message, self.max_tokens)
        items: list[TurnContextItem] = [
            TurnContextItem(
                source_type="current_message",
                content=bounded_current_message,
                priority=100,
                token_size=_estimate_tokens(bounded_current_message),
            )
        ]

        def _filter_user(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
            if not entries or not user_id:
                return entries or []
            return [
                e
                for e in entries
                if not (
                    isinstance(e, dict)
                    and (e.get("user_id") or e.get("userId"))
                    and (e.get("user_id") != user_id and e.get("userId") != user_id)
                )
            ]

        safe_memories = _filter_user(memories)
        safe_messages = _filter_user(recent_messages)
        safe_tool_results = _filter_user(tool_results)
        safe_projects = _filter_user([project] if project else [])

        for source_type, values, priority in (
            ("summary", [summary] if summary else [], 80),
            ("project", safe_projects, 70),
            ("memory", safe_memories, 50),
            ("message", safe_messages, 40),
            ("tool_result", safe_tool_results, 30),
        ):
            for value in values:
                content = (
                    value
                    if isinstance(value, str)
                    else str(value.get("content") or value.get("text") or value)
                )
                items.append(
                    TurnContextItem(
                        source_type=source_type,
                        source_id=value.get("id") if isinstance(value, dict) else None,
                        content=content,
                        priority=priority,
                        token_size=_estimate_tokens(content),
                    )
                )
        kept: list[TurnContextItem] = []
        budget = max(0, self.max_tokens - items[0].token_size)
        for item in sorted(
            items[1:], key=lambda x: (-x.priority, x.source_type, x.source_id or "")
        ):
            if item.token_size <= budget:
                kept.append(item)
                budget -= item.token_size
        ordered = [items[0]] + sorted(
            kept, key=lambda x: (-x.priority, x.source_type, x.source_id or "")
        )
        return TurnContext(
            current_message=current_message,
            items=ordered,
            attachments=list(attachments or []),
            token_estimate=sum(i.token_size for i in ordered),
        )
