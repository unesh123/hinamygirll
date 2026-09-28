"""HINA ASTRA — Executive Router (§7).

Evaluates the canonical AstraContext snapshot and classifies the execution route:
- CHAT: Conversational, explanatory, creative, or reasoning turns without tool mutation.
- DIRECT_ACTION: Deterministic, single-capability executions (e.g., reminders, image gen, code run, doc gen).
- AGENT_RUN: Multi-step autonomous goals, deep research, or iterative workflows.
- WORKSPACE: Contextual code manipulation, active file edits, or website/app creation tasks.
- CLARIFICATION: Missing critical parameters or ambiguous requests without active context.
"""

from __future__ import annotations

import re
from typing import Sequence

from .types import (
    AstraContext,
    AstraRoute,
    RouteDecision,
)


# Interrogative or educational phrasing that implies discussion rather than action
_EDUCATIONAL_OR_INQUIRY_PATTERNS = (
    r"\b(how\s+to|how\s+do\s+I|how\s+does|what\s+is|what\s+are|what\s+does|meaning\s+of|define|"
    r"why\s+did|why\s+does|can\s+you\s+explain|tell\s+me\s+about|is\s+it\s+possible|do\s+not|don't|dont|never)\b"
)

# Multi-step agent phrasing
_AGENT_PATTERNS = (
    r"^\s*/(agent|deep|plan|workflow)\b|"
    r"\b(deep\s+research|audit\s+the\s+entire|audit\s+the\s+whole|refactor\s+the\s+entire|"
    r"step\s+by\s+step\s+plan\s+and\s+execute|build\s+a\s+full|build\s+an\s+entire)\b"
)


class AstraExecutiveRouter:
    """Classifies user intent against the compiled context into an execution route."""

    def route(self, context: AstraContext) -> RouteDecision:
        user_text = (context.request.input.text or "").strip()
        lower_text = user_text.lower()

        # 1. Check for explicit slash commands first
        if re.search(r"^\s*/(deep|agent|workflow|plan)\b", lower_text):
            return RouteDecision(
                route=AstraRoute.AGENT_RUN,
                confidence=1.0,
                goal=user_text,
                candidate_capabilities=["agent.kernel", "web.search"],
                reasoning="Explicit agent command requested.",
            )

        if re.search(r"^\s*/(image|draw|img|generate)\b", lower_text):
            return RouteDecision(
                route=AstraRoute.DIRECT_ACTION,
                confidence=1.0,
                goal=user_text,
                candidate_capabilities=["image.generate"],
                reasoning="Explicit image command requested.",
            )

        # 2. Check for underspecified requests requiring clarification (Case I)
        if re.search(r"^\s*(make|fix|change|improve|do)\s+(it|this|that)\s+(better|faster|nicer|more|different)\b", lower_text):
            has_active_referent = bool(
                context.entities.get("active")
                or context.active_object
                or (context.workspace and context.workspace.active_file)
            )
            if not has_active_referent:
                return RouteDecision(
                    route=AstraRoute.CLARIFICATION,
                    confidence=0.95,
                    goal=user_text,
                    candidate_capabilities=[],
                    reasoning="Underspecified referent ('it') with no active entity, object, or workspace context.",
                )

        # 3. Check for Website / App Creation -> WORKSPACE Promotion (Case F)
        if re.search(r"\b(build|create|code|develop)\s+(?:me\s+)?(?:an?\s+)?(?:[\w-]+\s+){0,3}(landing\s+page|website|web\s+app|dashboard)\b", lower_text):
            return RouteDecision(
                route=AstraRoute.WORKSPACE,
                confidence=0.95,
                goal=user_text,
                candidate_capabilities=["workspace.create", "code.write"],
                reasoning="Website/App creation request promoted to Workspace route.",
            )

        # 4. Check for Workspace context & commands
        if context.workspace and (
            context.workspace.active_file
            or context.workspace.selected_range
            or context.workspace.preview_selection
        ):
            # If user refers to "this file", "in this component", "edit line", etc.
            if re.search(r"\b(this\s+file|selected|preview|diff|edit\s+line|fix\s+line|component)\b", lower_text):
                return RouteDecision(
                    route=AstraRoute.WORKSPACE,
                    confidence=0.95,
                    goal=user_text,
                    candidate_capabilities=["workspace.edit", "workspace.diff"],
                    reasoning="Workspace context active and referenced by user query.",
                )

        # 5. Check for multi-step agent triggers
        if re.search(_AGENT_PATTERNS, lower_text):
            return RouteDecision(
                route=AstraRoute.AGENT_RUN,
                confidence=0.9,
                goal=user_text,
                candidate_capabilities=["agent.kernel"],
                reasoning="Autonomous multi-step execution pattern detected.",
            )

        # 6. Check for inquiry / educational bypass (e.g. Case G: "what does a reminder mean?")
        is_inquiry = bool(re.search(_EDUCATIONAL_OR_INQUIRY_PATTERNS, lower_text))

        if not is_inquiry:
            # Check for direct action capability triggers

            # Document generation (Case E)
            if re.search(r"\b(create|generate|write|make|draft)\s+(?:me\s+)?(?:a\s+)?(?:comprehensive\s+)?(?:document|doc|report|pdf|article|paper)\b", lower_text):
                return RouteDecision(
                    route=AstraRoute.DIRECT_ACTION,
                    confidence=0.95,
                    goal="Generate document",
                    candidate_capabilities=["document.generate"],
                    reasoning="Document generation request detected.",
                )

            # Reminder creation (Case H)
            if re.search(r"\b(remind\s+me|set\s+(?:a\s+)?reminder|schedule\s+(?:a\s+)?reminder)\b", lower_text):
                return RouteDecision(
                    route=AstraRoute.DIRECT_ACTION,
                    confidence=0.95,
                    goal="Schedule reminder",
                    candidate_capabilities=["reminders.create"],
                    reasoning="Imperative reminder scheduling detected.",
                )

            # Image search (Case C)
            if re.search(r"\b(?:show|get|fetch|find|give\s+me)\s+(?:me\s+)?(?:more\s+)?(?:images?|pics?|pictures?|photos?)\b", lower_text):
                return RouteDecision(
                    route=AstraRoute.DIRECT_ACTION,
                    confidence=0.95,
                    goal="Search images",
                    candidate_capabilities=["image.search", "image.generate"],
                    reasoning="Image search request detected.",
                )

            # Image generation (Case D)
            if re.search(r"\b(generate|draw|create|paint)\s+(?:an?\s+)?(?:cinematic\s+|realistic\s+)?(?:image|picture|artwork|illustration|portrait|wallpaper|photo)\b", lower_text):
                return RouteDecision(
                    route=AstraRoute.DIRECT_ACTION,
                    confidence=0.95,
                    goal="Generate image",
                    candidate_capabilities=["image.generate"],
                    reasoning="Direct image generation request detected.",
                )

            # Code execution
            if re.search(r"^\s*```(python|bash|sh|py)", user_text) or re.search(r"\b(run|execute)\s+(?:this\s+)?(?:code|python|script)\b", lower_text):
                return RouteDecision(
                    route=AstraRoute.DIRECT_ACTION,
                    confidence=0.90,
                    goal="Run code",
                    candidate_capabilities=["code.run"],
                    reasoning="Direct code execution request detected.",
                )

            # High confidence candidate capability from registry
            top_candidates = [c for c in context.capabilities if c.relevance_score >= 4.0]
            if top_candidates:
                top_id = top_candidates[0].capability_id
                # Check if query is actionable
                if any(w in lower_text for w in ["search", "find", "look up", "generate", "create", "run", "remind"]):
                    return RouteDecision(
                        route=AstraRoute.DIRECT_ACTION,
                        confidence=0.85,
                        goal=user_text,
                        candidate_capabilities=[top_id],
                        reasoning=f"High relevance capability match ({top_id}) with imperative intent.",
                    )

        # 7. Default to CHAT (Cases A, B, G)
        return RouteDecision(
            route=AstraRoute.CHAT,
            confidence=1.0,
            goal=user_text,
            candidate_capabilities=[c.capability_id for c in context.capabilities[:3]],
            reasoning="Conversational dialogue flow.",
        )
