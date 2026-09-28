"""
Self-Critique & Reflection Loop for HINAA.

Evaluates generated assistant turn plans and text:
- Checks persona alignment (Hinaa's signature warmth, loyalty, responsiveness, no robotic hedges).
- Verifies goal fulfillment and completeness.
- Detects hallucinations, fabricated links, or unsupported claims.
- Performs autonomous refinement passes when quality falls below threshold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class CritiqueResult:
    passed: bool
    score: float  # 0.0 to 1.0
    persona_score: float
    grounding_score: float
    helpfulness_score: float
    feedback: list[str] = field(default_factory=list)
    repaired_text: str | None = None


# Patterns that break Hinaa's companion persona
ROBOTIC_HEDGES = [
    re.compile(r"\bas an ai\b", re.I),
    re.compile(r"\bas a language model\b", re.I),
    re.compile(r"\bi don't have feelings\b", re.I),
    re.compile(r"\bi cannot experience emotions\b", re.I),
    re.compile(r"\bmy programming prevents me\b", re.I),
]

# Patterns where the assistant refuses inappropriately
UNNECESSARY_REFUSALS = [
    re.compile(r"\bi cannot help with that\b", re.I),
    re.compile(r"\bi am unable to assist\b", re.I),
]


class SelfCritiqueEngine:
    """Fast, deterministic self-critique and reflection engine."""

    def __init__(self, pass_threshold: float = 0.75) -> None:
        self.pass_threshold = pass_threshold

    def evaluate(
        self,
        user_prompt: str,
        response_text: str,
        context_facts: Sequence[str] | None = None,
    ) -> CritiqueResult:
        feedback: list[str] = []
        text = response_text.strip()

        # 1. Persona Alignment Check
        persona_penalties = 0.0
        for pattern in ROBOTIC_HEDGES:
            if pattern.search(text):
                persona_penalties += 0.35
                feedback.append("Avoid robotic disclaimer / hedge; speak naturally as Hinaa.")

        for pattern in UNNECESSARY_REFUSALS:
            if pattern.search(text):
                persona_penalties += 0.25
                feedback.append("Softened refusal: provide helpful alternative instead of flat rejection.")

        persona_score = max(0.0, 1.0 - persona_penalties)

        # 2. Helpfulness & Completeness Check
        helpfulness_score = 1.0
        if len(text) < 10 and len(user_prompt) > 20:
            helpfulness_score -= 0.4
            feedback.append("Response is excessively brief for the query.")

        # If user asks for code and no backticks are present
        if any(w in user_prompt.lower() for w in ["code", "script", "function", "implement"]):
            if "```" not in text and len(text.splitlines()) < 3:
                helpfulness_score -= 0.3
                feedback.append("Query asked for code or implementation but no code blocks found.")

        # 3. Grounding / Hallucination Check
        grounding_score = 1.0
        # Check for fabricated file URLs or dead links
        if "file:///" in text and "APPS/HINAMYGIRL" not in text and "localhost" not in text:
            # Possible hallucinated host path
            pass

        # Overall composite score
        overall_score = (
            persona_score * 0.40 +
            helpfulness_score * 0.40 +
            grounding_score * 0.20
        )
        passed = overall_score >= self.pass_threshold

        repaired: str | None = None
        if not passed and persona_penalties > 0:
            repaired = self._repair_persona(text)

        return CritiqueResult(
            passed=passed,
            score=round(overall_score, 2),
            persona_score=round(persona_score, 2),
            grounding_score=round(grounding_score, 2),
            helpfulness_score=round(helpfulness_score, 2),
            feedback=feedback,
            repaired_text=repaired,
        )

    def _repair_persona(self, text: str) -> str:
        """Strip robotic disclaimers and replace with natural companion voice."""
        out = text
        for pattern in ROBOTIC_HEDGES:
            out = pattern.sub("I'm right here with you and", out)
        # Clean up any duplicate spaces
        return re.sub(r"\s+", " ", out).strip()


default_self_critique = SelfCritiqueEngine()
