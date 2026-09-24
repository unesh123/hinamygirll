from __future__ import annotations

import re
from enum import Enum
from typing import Any


class AnswerDepth(str, Enum):
    QUICK = "QUICK"
    STANDARD = "STANDARD"
    DETAILED = "DETAILED"
    DEEP = "DEEP"
    EXHAUSTIVE = "EXHAUSTIVE"
    ARTIFACT = "ARTIFACT"


class AnswerDepthController:
    """Infers appropriate answer depth so HINAA provides concise answers for simple queries
    and deep, comprehensive breakdowns for complex questions automatically."""

    @staticmethod
    def infer_depth(query: str, *, active_goal: Any | None = None) -> AnswerDepth:
        cleaned = query.strip()
        lowered = cleaned.lower()

        # 1. Quick indicators: Greetings, thanks, simple math, or explicit brevity
        if re.search(r"^(?:hi|hey|hello|namaste|नमस्ते|thanks|thank\s+you|good\s+morning|good\s+evening)(?:\s+(?:hina|hinaa|there|babe|bot))?[!?,.]*$", lowered):
            return AnswerDepth.QUICK

        if len(cleaned) <= 45 and re.search(r"^(?:what\s+is\s+[\d\s+\-*/xX]+|\d+\s*[+\-*/xX]\s*\d+|capital\s+of\s+[a-z]+|who\s+is\s+the\s+president\s+of\s+[a-z]+)[!?,.]*$", lowered):
            return AnswerDepth.QUICK

        if re.search(r"\b(briefly|in\s+one\s+sentence|quick\s+answer|tl;?dr|short\s+summary)\b", lowered):
            return AnswerDepth.QUICK

        # 2. Artifact & Exhaustive indicators
        if re.search(r"\b(?:10,?000\s+lines|full\s+report|complete\s+(?:implementation\s+)?specification|entire\s+(?:engineering\s+)?specification|exhaustive|full\s+spec|full\s+documentation|every\s+single|all\s+edge\s+cases)\b", lowered):
            return AnswerDepth.EXHAUSTIVE

        # 3. Deep indicators: Active goals, system design, architectural recommendations, multi-source comparisons
        if active_goal is not None:
            return AnswerDepth.DEEP

        if re.search(r"\b(design\s+(?:the\s+)?(?:ideal\s+)?.*architecture|deep\s+dive|in-?depth|architecture|system\s+design|production\s+design|compare\s+(?:options|architectures)|trade-?offs|root\s+cause\s+analysis|step-by-step\s+implementation|comprehensive\s+guide|distributed\s+consensus)\b", lowered):
            return AnswerDepth.DEEP

        # 4. Detailed indicators: How mechanisms work, multi-step explanations, pros & cons
        if re.search(r"\b(how\s+does\s+.*\s+work|explain\s+how|break\s+down|pros\s+and\s+cons|compare|differences?\s+between|tutorial|guide|walkthrough|what\s+are\s+the\s+steps)\b", lowered):
            return AnswerDepth.DETAILED

        # 5. Default fallback: Standard
        return AnswerDepth.STANDARD

    @staticmethod
    def get_depth_instruction(depth: AnswerDepth) -> str:
        instructions = {
            AnswerDepth.QUICK: "Respond concisely in 1-3 sentences. Focus strictly on the direct answer without preamble.",
            AnswerDepth.STANDARD: "Provide a clear, conversational response in 1-2 focused paragraphs with direct substance.",
            AnswerDepth.DETAILED: "Provide a structured response with clear sections, code examples where applicable, and key technical mechanics.",
            AnswerDepth.DEEP: "Provide a deep multi-dimensional analysis including architecture diagrams/sections, production trade-offs, edge cases, and concrete implementation patterns.",
            AnswerDepth.EXHAUSTIVE: "Provide an exhaustive, publication-grade specification covering all components, contracts, invariants, edge cases, and failure modes.",
            AnswerDepth.ARTIFACT: "Provide an end-to-end durable specification structured as a standalone engineering document.",
        }
        return instructions.get(depth, instructions[AnswerDepth.STANDARD])

