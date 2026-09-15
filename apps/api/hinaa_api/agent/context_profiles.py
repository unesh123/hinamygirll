"""HINAA Phase B2 — Context profiles and memory query router.

Directive §16/§17/§18/§35: profiles bound what the compiler will pull;
the query router decides which retrieval routes a turn actually needs so a
simple "yes" never triggers heavy historical/vector retrieval.

MAX profile does NOT mean "fill the context window" — it raises retrieval
budgets and allows larger hierarchical expansion while keeping ranking,
dedup, trust separation, and the output-token reserve intact (§50).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ContextProfile(str, Enum):
    FAST = "FAST"            # hot state only; no heavy retrieval
    STANDARD = "STANDARD"    # hot + relevant warm (default)
    DEEP = "DEEP"            # larger memory/RAG/repository retrieval
    MAX = "MAX"              # large hierarchical expansion, still compiled


# Directive §35 — adaptive source budget shares per profile. Values are
# defaults, not hardcoded law: callers may override via SourceBudgets.
@dataclass(frozen=True)
class ProfileBudgets:
    profile: ContextProfile
    system: float = 0.10
    live_state: float = 0.35
    recent_turns: float = 0.30
    task_project: float = 0.10
    memory: float = 0.10
    knowledge: float = 0.05   # RAG / repository / files
    history: float = 0.00

    @property
    def as_shares(self) -> dict[str, float]:
        return {
            "system": self.system,
            "live_state": self.live_state,
            "recent_turns": self.recent_turns,
            "task_project": self.task_project,
            "memory": self.memory,
            "knowledge": self.knowledge,
            "history": self.history,
        }


PROFILE_BUDGETS: dict[ContextProfile, ProfileBudgets] = {
    ContextProfile.FAST: ProfileBudgets(
        profile=ContextProfile.FAST,
        system=0.12,
        live_state=0.40,
        recent_turns=0.48,
        task_project=0.00,
        memory=0.00,
        knowledge=0.00,
        history=0.00,
    ),
    ContextProfile.STANDARD: ProfileBudgets(
        profile=ContextProfile.STANDARD,
        system=0.10,
        live_state=0.35,
        recent_turns=0.30,
        task_project=0.10,
        memory=0.10,
        knowledge=0.05,
        history=0.00,
    ),
    ContextProfile.DEEP: ProfileBudgets(
        profile=ContextProfile.DEEP,
        system=0.08,
        live_state=0.20,
        recent_turns=0.20,
        task_project=0.12,
        memory=0.20,
        knowledge=0.20,
        history=0.00,
    ),
    ContextProfile.MAX: ProfileBudgets(
        profile=ContextProfile.MAX,
        system=0.06,
        live_state=0.15,
        recent_turns=0.20,
        task_project=0.10,
        memory=0.20,
        knowledge=0.25,
        history=0.04,
    ),
}

# Domain adjustments layered on the profile defaults (§35: RESEARCH/CODING).
DOMAIN_BUDGET_OVERRIDES: dict[str, dict[str, float]] = {
    "research": {"live_state": 0.10, "task_project": 0.10, "knowledge": 0.55, "recent_turns": 0.10, "memory": 0.15},
    "coding": {"live_state": 0.10, "task_project": 0.20, "knowledge": 0.45, "recent_turns": 0.10, "memory": 0.15},
}

# Directive §33 — never fill input so completely that output cannot finish.
DEFAULT_OUTPUT_RESERVE_TOKENS = 4_096
DEFAULT_SAFETY_MARGIN_TOKENS = 512


class QueryRoute(str, Enum):
    """Directive §18 — which retrieval routes a turn requires."""

    NONE = "NONE"
    HOT = "HOT"
    PROJECT = "PROJECT"
    ENTITY = "ENTITY"
    ASSET = "ASSET"
    GLOBAL_MEMORY = "GLOBAL_MEMORY"
    RAG = "RAG"
    REPOSITORY = "REPOSITORY"
    HISTORICAL = "HISTORICAL"
    EXACT_SOURCE = "EXACT_SOURCE"


_TRIVIAL_RE = re.compile(
    r"^(hi+|hello+|hey+|yo|ok(ay)?|k|kk|thanks|thank you|thx|ty|yes|no|yeah|yep|nope|"
    r"sure|cool|nice|great|got it|okay|alright|done|hmm+|hm+|lol|haha+|"
    r"namaste|k cha|thik cha|thik chha)[!., ]*$",
    re.IGNORECASE,
)
_HISTORICAL_RE = re.compile(
    r"\b(what did i (say|tell|ask|mention)|earlier (today|yesterday|last week)|"
    r"yesterday|last week|last month|a (week|month|year) ago|previously (mentioned|said|discussed))\b",
    re.IGNORECASE,
)
_EXACT_RE = re.compile(
    r"\b(exactly|word for word|verbatim|exact(ly)? (words|quote|text|what i said))\b",
    re.IGNORECASE,
)
_REPO_RE = re.compile(
    r"\b(where is|which file|which function|how does (the )?(code|repo)|login|auth|"
    r"middleware|endpoint|bug|traceback|stack trace|fix the|refactor|tests? fail)\b",
    re.IGNORECASE,
)
_PROJECT_RE = re.compile(
    r"\b(continue (the )?(project|work|auth|nova|mika)|our (project|architecture|app|system)|"
    r"the (project|repo|codebase)|nova|mika|resume (work|the task))\b",
    re.IGNORECASE,
)
_ASSET_RE = re.compile(
    r"\b(my (asset|reference|image|character|avatar)|use (the|my) (reference|mikasa|asset)|"
    r"that (image|asset|character)|second one|first one|the other (one|image))\b",
    re.IGNORECASE,
)
_ENTITY_RE = re.compile(
    r"\b(who is|tell me about|remember (him|her|them|when)|my (friend|sister|brother|mom|dad)|"
    r"\w+('s)? birthday)\b",
    re.IGNORECASE,
)
_RAG_RE = re.compile(
    r"\b(search|latest|current|today'?s|news|according to|sources?|research|documentation|docs? for)\b",
    re.IGNORECASE,
)
_MEMORY_RE = re.compile(
    r"\b(do you remember|what do you know about|i told you|we discussed|my (preference|favorite))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RouteDecision:
    routes: tuple[QueryRoute, ...]
    profile: ContextProfile
    domain: str
    reason: str

    @property
    def is_trivial(self) -> bool:
        return self.routes in ((QueryRoute.NONE,), (QueryRoute.HOT,))


class MemoryQueryRouter:
    """Classify a turn into retrieval routes + profile (§18, §39–§46)."""

    def route(
        self,
        user_text: str,
        *,
        has_active_task: bool = False,
        has_active_project: bool = False,
        has_selected_asset: bool = False,
        domain_hint: str | None = None,
        explicit_profile: ContextProfile | str | None = None,
    ) -> RouteDecision:
        text = (user_text or "").strip()

        # Explicit profile always wins (developer/agent override).
        # NOTE: only true trivial acknowledgments route FAST — short but
        # meaningful commands ("Summarize.", "go on") must keep STANDARD so
        # they still compile recent history (§39 guards latency, not content).
        if explicit_profile is not None:
            profile = ContextProfile(explicit_profile)
        elif _TRIVIAL_RE.match(text):
            profile = ContextProfile.FAST
        else:
            profile = ContextProfile.STANDARD

        if profile is ContextProfile.FAST and _TRIVIAL_RE.match(text):
            routes: tuple[QueryRoute, ...] = (QueryRoute.HOT,)
            return RouteDecision(
                routes=routes,
                profile=profile,
                domain=domain_hint or "chat",
                reason="trivial turn — hot context only, no heavy retrieval (§39)",
            )

        found: list[QueryRoute] = [QueryRoute.HOT]

        if _EXACT_RE.search(text):
            found.append(QueryRoute.EXACT_SOURCE)
        if _HISTORICAL_RE.search(text):
            found.append(QueryRoute.HISTORICAL)
        if _REPO_RE.search(text) or domain_hint == "coding":
            found.append(QueryRoute.REPOSITORY)
        if _ASSET_RE.search(text) or has_selected_asset:
            found.append(QueryRoute.ASSET)
        if _ENTITY_RE.search(text):
            found.append(QueryRoute.ENTITY)
        if _PROJECT_RE.search(text) or has_active_task or has_active_project:
            found.append(QueryRoute.PROJECT)
        if _MEMORY_RE.search(text):
            found.append(QueryRoute.GLOBAL_MEMORY)
        if _RAG_RE.search(text) or profile in (ContextProfile.DEEP, ContextProfile.MAX):
            found.append(QueryRoute.RAG)

        # Order routes from hottest to coldest for deterministic traces.
        order = [
            QueryRoute.HOT, QueryRoute.ASSET, QueryRoute.PROJECT, QueryRoute.ENTITY,
            QueryRoute.GLOBAL_MEMORY, QueryRoute.RAG, QueryRoute.REPOSITORY,
            QueryRoute.HISTORICAL, QueryRoute.EXACT_SOURCE,
        ]
        routes = tuple(sorted(set(found), key=order.index))

        domain = domain_hint or self._infer_domain(text)
        return RouteDecision(
            routes=routes,
            profile=profile,
            domain=domain,
            reason=f"routes={','.join(r.value for r in routes)}",
        )

    @staticmethod
    def _infer_domain(text: str) -> str:
        lowered = text.lower()
        if _REPO_RE.search(text):
            return "coding"
        if _RAG_RE.search(text):
            return "research"
        if re.search(r"\b(summarize|write|document|spec|report|essay|draft)\b", lowered):
            return "document"
        return "chat"


def effective_budgets(
    profile: ContextProfile,
    *,
    domain: str | None = None,
) -> dict[str, float]:
    """Profile shares with optional domain override, normalized to 1.0."""
    shares = dict(PROFILE_BUDGETS[profile].as_shares)
    if domain and domain in DOMAIN_BUDGET_OVERRIDES:
        shares.update(DOMAIN_BUDGET_OVERRIDES[domain])
    total = sum(shares.values()) or 1.0
    return {k: v / total for k, v in shares.items()}


def compute_input_budget(
    model_context_limit: int,
    *,
    expected_output_tokens: int = DEFAULT_OUTPUT_RESERVE_TOKENS,
    safety_margin: int = DEFAULT_SAFETY_MARGIN_TOKENS,
) -> int:
    """Directive §33: input_budget = limit − output_reserve − safety_margin."""
    return max(0, model_context_limit - expected_output_tokens - safety_margin)
