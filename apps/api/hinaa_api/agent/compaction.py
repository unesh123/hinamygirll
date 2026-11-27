"""Context window compaction preserving raw tool results verbatim."""
from __future__ import annotations

import json
import math
from typing import Any


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate prompt tokens deterministically from serialized message payloads."""
    total_chars = 0
    for msg in messages:
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, str):
                total_chars += len(content)
            else:
                total_chars += len(json.dumps(content, ensure_ascii=False, default=str))
            total_chars += 16
        else:
            total_chars += len(str(msg))
    return math.ceil(total_chars / 4)


def summarize(conversational: list[dict[str, Any]]) -> str:
    """Summarize non-tool conversational messages without fabricating unseen details."""
    lines: list[str] = []
    for m in conversational:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "user")
        content = m.get("content")
        text = (
            content
            if isinstance(content, str)
            else json.dumps(content, ensure_ascii=False, default=str)
        )
        snippet = " ".join(text.strip().split())[:200]
        if snippet:
            lines.append(f"- [{role}] {snippet}")
    return "\n".join(lines[-20:]) or "(no prior conversational messages)"


def compact(
    messages: list[dict[str, Any]],
    keep_recent: int = 6,
    budget: int = 120_000,
) -> list[dict[str, Any]]:
    """Compact older chat turns when over budget while keeping tool results verbatim."""
    if estimate_tokens(messages) <= budget or keep_recent <= 0 or len(messages) <= keep_recent:
        return messages

    head, tail = messages[:-keep_recent], messages[-keep_recent:]
    tool_roles = ("tool", "tool_observation")
    preserved = [m for m in head if isinstance(m, dict) and m.get("role") in tool_roles]
    conversational = [
        m for m in head if not (isinstance(m, dict) and m.get("role") in tool_roles)
    ]

    summary = summarize(conversational)
    return [
        {"role": "system", "content": f"Earlier context:\n{summary}"},
        *preserved,
        *tail,
    ]
