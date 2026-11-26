"""Live concurrent voice orchestrator + voice-friendly prose summarizer."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from ..intent_router import ROUTE_CHAT, RouteDecision, route_intent

_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_MD_SYNTAX_RE = re.compile(r"(?:^#+\s*|[*_~>|]+)", re.MULTILINE)
_URL_RE = re.compile(r"https?://\S+")


def summarize_for_voice(text: str, *, max_chars: int = 240) -> str:
    """Strip markdown, code fences, and URLs into natural speakable prose."""
    cleaned = _CODE_BLOCK_RE.sub(" I've shown the code in chat. ", str(text or ""))
    cleaned = _MD_LINK_RE.sub(r"\1", cleaned)
    cleaned = _URL_RE.sub("", cleaned)
    cleaned = _INLINE_CODE_RE.sub(r"\1", cleaned)
    cleaned = _MD_SYNTAX_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    # Cut cleanly at sentence boundary if possible
    cutoff = cleaned[:max_chars]
    last_dot = max(cutoff.rfind("."), cutoff.rfind("!"), cutoff.rfind("?"))
    if last_dot >= max_chars // 2:
        return cutoff[: last_dot + 1].strip()
    return cutoff.rstrip(" ,;:") + "..."


@dataclass
class LiveTurnOutcome:
    route: RouteDecision
    spoken_intro: str
    spoken_result: str
    background_task: asyncio.Task[Any] | None = None


class LiveOrchestrator:
    """Runs speech immediately and executes multi-step tools concurrently without blocking."""

    def __init__(
        self,
        *,
        chat_fn: Callable[[str], Awaitable[str]] | None = None,
        tool_fn: Callable[[str, RouteDecision], Awaitable[str]] | None = None,
    ) -> None:
        self._chat_fn = chat_fn
        self._tool_fn = tool_fn
        self._bg_tasks: set[asyncio.Task[Any]] = set()

    async def handle_utterance(
        self,
        utterance: str,
        *,
        on_tool_result: Callable[[str], Awaitable[None]] | None = None,
    ) -> LiveTurnOutcome:
        decision = route_intent(utterance)

        if decision.route == ROUTE_CHAT:
            reply = (
                await self._chat_fn(utterance)
                if self._chat_fn is not None
                else f"Got it — {utterance.strip()}"
            )
            return LiveTurnOutcome(
                route=decision,
                spoken_intro=summarize_for_voice(reply),
                spoken_result=summarize_for_voice(reply),
                background_task=None,
            )

        intro = summarize_for_voice(f"On it — running {decision.route.replace('_', ' ')} for you.")

        async def _run_tool() -> str:
            res = (
                await self._tool_fn(utterance, decision)
                if self._tool_fn is not None
                else f"Finished {decision.route}."
            )
            spoken = summarize_for_voice(res)
            if on_tool_result is not None:
                await on_tool_result(spoken)
            return spoken

        task = asyncio.create_task(_run_tool())
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

        return LiveTurnOutcome(
            route=decision,
            spoken_intro=intro,
            spoken_result="",
            background_task=task,
        )

    def cancel_all(self) -> None:
        for t in list(self._bg_tasks):
            if not t.done():
                t.cancel()
        self._bg_tasks.clear()
