"""Intent-Aware Follow-Up Policy — Eliminates mandatory blanket "Next Steps" filler.

Replaces uniform next-steps boilerplate with an intent-driven policy:
- NONE: Pure answers, direct facts, or explicit requests for no follow-up. Zero filler.
- MINIMAL: Completed artifacts, quick confirmations, at most one brief natural next step.
- SUGGEST: Strategic reports, exploratory queries, research deep-dives with decision branches.
- ACTIONABLE: In-flight workflows, procedural coding, multi-step execution tasks.
"""

from __future__ import annotations

import re
from enum import Enum


class FollowUpPolicy(str, Enum):
    """Granular follow-up policy based on turn intent and user preference."""

    NONE = "none"
    MINIMAL = "minimal"
    SUGGEST = "suggest"
    ACTIONABLE = "actionable"


_EXPLICIT_NO_FOLLOWUP_RE = re.compile(
    r"\b(?:just\s+(?:give\s+me|tell\s+me|answer)|no\s+(?:follow[\s-]?ups?|next\s+steps?|suggestions?)|direct\s+answer|only\s+answer|don't\s+suggest)\b",
    re.IGNORECASE,
)


def resolve_followup_policy(
    user_text: str,
    turn_intent: str = "conversational",
    *,
    has_artifact: bool = False,
    is_code: bool = False,
) -> FollowUpPolicy:
    """Resolve the appropriate FollowUpPolicy for a turn."""
    text = (user_text or "").strip()

    # Explicit user instruction outranks everything
    if _EXPLICIT_NO_FOLLOWUP_RE.search(text):
        return FollowUpPolicy.NONE

    intent_lower = (turn_intent or "").lower()

    if intent_lower in {"minimal", "clarification", "safety_redirect", "short_full", "direct"}:
        return FollowUpPolicy.NONE

    if has_artifact or intent_lower in {"artifact_ready", "completion", "code_result"}:
        return FollowUpPolicy.MINIMAL

    if intent_lower in {"procedural", "actionable", "workflow", "in_flight"}:
        return FollowUpPolicy.ACTIONABLE

    if intent_lower in {"report", "explanatory", "research_report", "technical_report", "decision_memo"}:
        return FollowUpPolicy.SUGGEST

    # Short questions default to NONE or MINIMAL
    if len(text) < 40 and not any(w in text.lower() for w in ("plan", "guide", "roadmap", "architecture", "strategy")):
        return FollowUpPolicy.NONE

    return FollowUpPolicy.MINIMAL


def render_followup_instructions(policy: FollowUpPolicy) -> str:
    """Render prompt instructions corresponding to the given FollowUpPolicy."""
    if policy == FollowUpPolicy.NONE:
        return (
            "- FOLLOW-UP POLICY (NONE): Do NOT append 'Next Steps', 'Follow-up Options', or concluding "
            "suggestions. Conclude cleanly once the substantive answer is delivered. Zero filler."
        )
    if policy == FollowUpPolicy.MINIMAL:
        return (
            "- FOLLOW-UP POLICY (MINIMAL): If helpful, you may suggest at most one natural follow-up "
            "option in a single brief sentence. Do not add a large section of speculative next steps."
        )
    if policy == FollowUpPolicy.SUGGEST:
        return (
            "- FOLLOW-UP POLICY (SUGGEST): Offer 2–3 focused, non-repetitive exploration or deep-dive "
            "options under a concise heading (e.g., '### Exploration Paths' or '### Strategic Options')."
        )
    if policy == FollowUpPolicy.ACTIONABLE:
        return (
            "- FOLLOW-UP POLICY (ACTIONABLE): Provide clear, numbered next implementation steps or "
            "executable commands to move the task forward."
        )
    return ""
