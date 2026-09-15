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


class AnswerDepthController:
    """Infers appropriate answer depth so HINAA provides concise answers for simple queries
    and deep, comprehensive breakdowns for complex questions automatically."""

    @staticmethod
    def infer_depth(query: str, *, active_goal: Any | None = None) -> AnswerDepth:
        cleaned = query.strip()
        lowered = cleaned.lower()

        # 1. Exhaustive indicators
        if re.search(r"\b(exhaustive|complete\s+specification|full\s+spec|full\s+documentation|every\s+single|entire\s+codebase|all\s+edge\s+cases)\b", lowered):
            return AnswerDepth.EXHAUSTIVE

        # 2. Deep indicators
        if active_goal is not None:
            return AnswerDepth.DEEP

        if re.search(r"\b(deep\s+dive|in-?depth|architecture|system\s+design|trade-?offs|root\s+cause\s+analysis|step-by-step\s+implementation|comprehensive\s+guide)\b", lowered):
            return AnswerDepth.DEEP

        # 3. Detailed indicators
        if re.search(r"\b(explain\s+how|break\s+down|pros\s+and\s+cons|compare|differences?\s+between|tutorial|guide|walkthrough|what\s+are\s+the\s+steps)\b", lowered):
            return AnswerDepth.DETAILED

        # 4. Quick indicators
        if len(cleaned) <= 40 and re.search(r"^(?:hi|hey|hello|good\s+morning|good\s+evening|what\s+is\s+[\d\s+\-*/xX]+|\d+\s*[+\-*/xX]\s*\d+|capital\s+of\s+[a-z]+|who\s+is\s+the\s+president\s+of\s+[a-z]+)[!?,.]*$", lowered):
            return AnswerDepth.QUICK

        if re.search(r"\b(briefly|in\s+one\s+sentence|quick\s+answer|tl;?dr|short\s+summary)\b", lowered):
            return AnswerDepth.QUICK

        return AnswerDepth.STANDARD

    @staticmethod
    def get_depth_instruction(depth: AnswerDepth) -> str:
        instructions = {
            AnswerDepth.QUICK: "Respond concisely in 1-3 sentences. Focus strictly on the direct answer without preamble.",
            AnswerDepth.STANDARD: "Provide a clear, conversational response in 1-2 focused paragraphs.",
            AnswerDepth.DETAILED: "Provide a structured response with explanatory sections, bullet points, and key considerations.",
            AnswerDepth.DEEP: "Provide a deep multi-dimensional analysis including architecture, trade-offs, edge cases, and code examples where helpful.",
            AnswerDepth.EXHAUSTIVE: "Provide an exhaustive, publication-grade specification covering all components, contracts, invariants, and failure modes.",
        }
        return instructions.get(depth, instructions[AnswerDepth.STANDARD])
