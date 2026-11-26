"""HINAA Intent Router — deterministic zero-LLM routing layer.

Classifies a user turn into an execution route before any model call so the
agent kernel can pick tools, plan depth and escalation without burning tokens
on trivial turns. Purely local, < 1ms, no I/O.

Routes (ordered by specificity; first decisive match wins, otherwise the
highest accumulated confidence):

- ``chat``            small talk, questions, opinions
- ``research``        web/deep research with sources
- ``coding``          write/fix/refactor code, repos, tests
- ``creative_media``  images, video, motion graphics, slides
- ``documents``       pdf/docx/report parsing or generation
- ``browser``         drive the live browser agent
- ``automation``      timers, reminders, split-bill style tool actions
- ``plan``            explicit multi-step orchestration

The router never executes anything; it only recommends. Confirmation
requirements are surfaced for mutation-class routes so the caller can honour
the approval policy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


ROUTE_CHAT = "chat"
ROUTE_RESEARCH = "research"
ROUTE_CODING = "coding"
ROUTE_CREATIVE = "creative_media"
ROUTE_DOCUMENTS = "documents"
ROUTE_BROWSER = "browser"
ROUTE_AUTOMATION = "automation"
ROUTE_PLAN = "plan"

ALL_ROUTES = (
    ROUTE_CHAT,
    ROUTE_RESEARCH,
    ROUTE_CODING,
    ROUTE_CREATIVE,
    ROUTE_DOCUMENTS,
    ROUTE_BROWSER,
    ROUTE_AUTOMATION,
    ROUTE_PLAN,
)

MUTATION_ROUTES = frozenset({ROUTE_CODING, ROUTE_CREATIVE, ROUTE_DOCUMENTS, ROUTE_AUTOMATION, ROUTE_PLAN})

# Per-route tool names. These must match names the agent kernel already
# registers; the router only suggests, never resolves implementations itself.
ROUTE_TOOLS: dict[str, tuple[str, ...]] = {
    ROUTE_CHAT: (),
    ROUTE_RESEARCH: ("web_search", "web_fetch", "synthesize_sources"),
    ROUTE_CODING: ("read_repo", "edit_files", "run_tests", "sandbox_exec"),
    ROUTE_CREATIVE: ("generate_image", "compose_video", "render_slides"),
    ROUTE_DOCUMENTS: ("parse_document", "generate_document"),
    ROUTE_BROWSER: ("browser_open", "browser_act", "browser_snapshot"),
    ROUTE_AUTOMATION: ("timer_start", "reminder_create", "calculator"),
    ROUTE_PLAN: ("plan_draft", "scheduler", "progress_tracker"),
}

# Phrases that switch a turn back to plain conversation even when a keyword
# elsewhere in the sentence would have matched a tool route.
_NEGATION_RE = re.compile(
    r"^(?:explain|describe|tell\s+me\s+about|how\s+(?:do|does|can|to)\b|why\b|what\s+(?:is|are|does)\b|"
    r"if\b|suppose\b|imagine\b|can\s+you\s+(?:explain|describe|tell)|do\s+not|don't|never|stop|cancel)\b",
    re.IGNORECASE,
)

_LONG_INPUT_CHARS = 12_000  # > this is a "big context" turn (e.g. pasted files)


def _hits(lower: str, *patterns: str) -> int:
    return sum(1 for p in patterns if re.search(p, lower) is not None)


@dataclass(frozen=True)
class RouteDecision:
    """Result of routing one user turn."""

    route: str
    confidence: float
    goal: str
    candidate_tools: tuple[str, ...] = field(default_factory=tuple)
    requires_planning: bool = False
    requires_confirmation: bool = False
    is_large_context: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "confidence": round(self.confidence, 4),
            "goal": self.goal,
            "candidate_tools": list(self.candidate_tools),
            "requires_planning": self.requires_planning,
            "requires_confirmation": self.requires_confirmation,
            "is_large_context": self.is_large_context,
            "metadata": dict(self.metadata),
        }


class IntentRouter:
    """Deterministic router. Thread-safe: no shared mutable state."""

    def route(self, text: str, *, context: dict[str, Any] | None = None) -> RouteDecision:
        value = str(text or "").strip()
        if not value:
            return RouteDecision(route=ROUTE_CHAT, confidence=0.99, goal="")

        lower = value.lower()
        is_large_context = len(value) > _LONG_INPUT_CHARS
        negated = _NEGATION_RE.search(value) is not None and not is_large_context

        # Explicit multi-step orchestration wins first: the user asked for a
        # coordinated run, not a single tool.
        if not negated and self._looks_like_plan(lower):
            return self._decision(ROUTE_PLAN, 0.93, value, planning=True, confirm=True, is_large_context=is_large_context)

        scores: list[tuple[float, str]] = []

        if not negated:
            if self._looks_like_browser(lower):
                scores.append((0.95, ROUTE_BROWSER))
            if self._looks_like_automation(lower):
                scores.append((0.92, ROUTE_AUTOMATION))
            if self._looks_like_documents(lower):
                scores.append((0.9, ROUTE_DOCUMENTS))
            if self._looks_like_creative(lower):
                scores.append((0.88, ROUTE_CREATIVE))
            if self._looks_like_coding(lower):
                scores.append((0.86, ROUTE_CODING))
            if self._looks_like_research(lower):
                scores.append((0.8, ROUTE_RESEARCH))

        if not scores:
            return self._chat_decision(value, negated=negated, is_large_context=is_large_context)

        scores.sort(reverse=True)
        top, route = scores[0]
        # Competing tool routes dampen confidence and force planning so the
        # planner can sequence them instead of guessing.
        competing = [r for _, r in scores if r != route]
        meta: dict[str, Any] = {"competing_routes": competing[:3]} if competing else {}
        if competing:
            top = min(top, 0.75)
            meta["reason"] = "multiple tool routes matched"
        return self._decision(
            route,
            top,
            value,
            planning=bool(competing) or route in {ROUTE_CODING, ROUTE_CREATIVE, ROUTE_DOCUMENTS},
            confirm=route in MUTATION_ROUTES,
            is_large_context=is_large_context,
            metadata=meta,
        )

    # ── route detectors ────────────────────────────────────────────────

    def _looks_like_plan(self, lower: str) -> bool:
        has_two_actions = (
            _hits(
                lower,
                r"\b(then|after that|and then|afterwards)\b",
                r"\b(step[- ]by[- ]step)\b",
                r"\b(first|second|third)\b.*\b(then|after)\b",
            )
            > 0
        )
        multiple_clauses = len(re.findall(r"[,;]", lower)) >= 2 and _hits(
            lower, r"\b(task|timer|remind|build|research|deploy|fix)\b"
        ) > 0
        explicit_plan = re.search(r"\b(plan|orchestrate|workflow|pipeline)\b", lower) is not None
        return (has_two_actions or multiple_clauses or explicit_plan) and _hits(
            lower, r"\b(build|create|fix|research|deploy|remind|timer|task|search)\b"
        ) > 0

    def _looks_like_browser(self, lower: str) -> bool:
        if lower.startswith("browser:") or lower.startswith("browse "):
            return True
        return (
            _hits(
                lower,
                r"\bopen\s+(youtube|spotify|google|wikipedia|amazon|netflix|github|gmail)\b",
                r"\b(play|search\s+on)\s+(youtube|spotify)\b",
                r"\b(click|navigate|scroll)\s+(on|to|down)\b",
                r"\bscreenshot\s+(of|the)\b",
            )
            > 0
        )

    def _looks_like_automation(self, lower: str) -> bool:
        return (
            _hits(
                lower,
                r"\b(timer|focus\s+session|pomodoro)\b",
                r"\b(remind|reminder|wake\s+me)\b",
                r"\bsplit\s+[\d,]+\b",
                r"\broll\s+\d*d\d+\b",
                r"\bflip\s+a?\s*coin\b",
            )
            > 0
        )

    def _looks_like_documents(self, lower: str) -> bool:
        return (
            _hits(
                lower,
                r"\b(pdf|docx|pptx|spreadsheet|xlsx|csv)\b",
                r"\b(report|whitepaper|contract|invoice)\b",
                r"\b(summari[sz]e|parse|extract)\s+(this|the)?\s*(document|file|paper)\b",
            )
            > 0
        )

    def _looks_like_creative(self, lower: str) -> bool:
        return (
            _hits(
                lower,
                r"\b(image|photo|illustration|logo|wallpaper|avatar)\b",
                r"\b(video|animation|motion\s+graphics|cinematic)\b",
                r"\b(slides?|presentation|deck)\b",
                r"\b(design|typography|poster|banner)\b",
            )
            > 0
        )

    def _looks_like_coding(self, lower: str) -> bool:
        return (
            _hits(
                lower,
                r"\b(code|function|class|bug|stack\s?trace|traceback|compile|typecheck)\b",
                r"\b(refactor|implement|unit\s?tests?|e2e)\b",
                r"\b(repo|repository|pull\s?request|commit|branch)\b",
                r"\b(website|webapp|web\s?app|api\s+endpoint|database)\b",
            )
            > 0
        )

    def _looks_like_research(self, lower: str) -> bool:
        return (
            _hits(
                lower,
                r"\b(search|look\s?up|find\s+out)\b",
                r"\b(latest|news|current|today'?s)\b",
                r"\b(compare|benchmark|market|competitor|trend)\b",
                r"\b(research|deep\s?research|investigate)\b",
            )
            > 0
        )

    # ── decision builders ──────────────────────────────────────────────

    def _chat_decision(self, value: str, *, negated: bool, is_large_context: bool) -> RouteDecision:
        # Questions that mention tools ("how do I split a bill?") stay chat.
        confidence = 0.7 if is_large_context else 0.95
        return RouteDecision(
            route=ROUTE_CHAT,
            confidence=confidence,
            goal=value[:2000],
            candidate_tools=(),
            requires_planning=False,
            requires_confirmation=False,
            is_large_context=is_large_context,
            metadata={"negated_tool_match": negated} if negated else {},
        )

    def _decision(
        self,
        route: str,
        confidence: float,
        value: str,
        *,
        planning: bool,
        confirm: bool,
        is_large_context: bool,
        metadata: dict[str, Any] | None = None,
    ) -> RouteDecision:
        return RouteDecision(
            route=route,
            confidence=confidence,
            goal=value[:2000],
            candidate_tools=ROUTE_TOOLS.get(route, ()),
            requires_planning=planning,
            requires_confirmation=confirm,
            is_large_context=is_large_context,
            metadata=metadata or {},
        )


_default_router = IntentRouter()


def route_intent(text: str, *, context: dict[str, Any] | None = None) -> RouteDecision:
    """Module-level convenience using the shared default router."""
    return _default_router.route(text, context=context)
