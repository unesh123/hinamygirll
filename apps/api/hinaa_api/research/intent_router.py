"""Request Intent & Freshness Router for Grounded Research.

Adheres to HINAA OS Phase 06 Directive §1:
- Classifies requests into Conversational, Factual Research, Time-Sensitive, Workspace Code, Multi-Hop, High-Stakes.
- Prevents forced RAG on casual conversation.
- Supports English, Nepali, Hindi, and code-switched queries.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from ..voice.multilingual import MultilingualNormalizer, LanguageClass
from .models import ResearchIntent


# Patterns for high-stakes queries
_HIGH_STAKES_PATTERNS = [
    re.compile(r"\b(medical\s+dosage|emergency|poison|suicide|exploit|zero[- ]day|credit\s+card|wire\s+transfer|legal\s+contract)\b", re.I),
]

# Patterns for multi-hop questions
_MULTI_HOP_PATTERNS = [
    re.compile(r"\b(?:who\s+(?:is|was)\s+the\s+(?:director|founder|ceo|author|president)\s+of\s+the\s+(?:company|movie|book|organization|country)\s+(?:that|which|whose))\b", re.I),
    re.compile(r"\b(?:what\s+is\s+the\s+capital\s+of\s+the\s+country\s+where)\b", re.I),
    re.compile(r"\b(?:compare\s+.*?\s+and\s+.*?\s+in\s+terms\s+of)\b", re.I),
    re.compile(r"\b(?:connection\s+between\s+.*?\s+and\s+.*?|relationship\s+between)\b", re.I),
]

# Patterns for time-sensitive public facts
_TEMPORAL_PATTERNS = [
    re.compile(r"\b(today|yesterday|this\s+week|current|currently|latest|recent|recently|breaking\s+news|what\s+happened\s+in|new\s+in\s+202[5-9]|price\s+of|stock\s+price|incident\s+in|earthquake\s+in|election\s+results)\b", re.I),
    re.compile(r"\b(आज|अहिले|हालको|ताजा|नयाँ|हालै|भर्खरै|समाचार)\b"), # Nepali/Hindi temporal markers
]

# Patterns for workspace / local repo
_WORKSPACE_PATTERNS = [
    re.compile(r"\b(?:file|folder|repo|repository|codebase|function|class|method|module|component|schema|migration)\b", re.I),
    re.compile(r"\b(?:in\s+this\s+project|in\s+our\s+code|where\s+is\s+.*?defined|how\s+does\s+.*?work\s+in\s+hinaa)\b", re.I),
    re.compile(r"\.(?:py|tsx?|jsx?|css|json|md|yaml|toml|sql)\b", re.I),
]

# Conversational greetings & persona chat
_CONVERSATIONAL_PATTERNS = [
    re.compile(r"^(?:hi|hello|hey|good\s+morning|good\s+evening|namaste|नमस्ते|सञ्चै\s+छौ|के\s+छ|how\s+are\s+you|what\s+are\s+you\s+doing|tell\s+me\s+a\s+joke)[.!?\s]*$", re.I),
    re.compile(r"^(?:who\s+are\s+you|what\s+is\s+your\s+name|are\s+you\s+hinaa|do\s+you\s+love\s+me)[.!?\s]*$", re.I),
]


@dataclass(slots=True)
class IntentRoutingDecision:
    intent: ResearchIntent
    needs_retrieval: bool
    freshness_required: bool
    language: LanguageClass
    search_query: str | None
    high_stakes: bool
    rationale: str


class ResearchIntentRouter:
    """Classifies user turn intent and decides optimal retrieval pathway."""

    @classmethod
    def route(cls, query: str) -> IntentRoutingDecision:
        cleaned = query.strip()
        lang = MultilingualNormalizer.detect_dominant_language(cleaned)

        if not cleaned:
            return IntentRoutingDecision(
                intent=ResearchIntent.CONVERSATIONAL,
                needs_retrieval=False,
                freshness_required=False,
                language=lang,
                search_query=None,
                high_stakes=False,
                rationale="empty_input",
            )

        # 1. High-Stakes Evaluation
        for pat in _HIGH_STAKES_PATTERNS:
            if pat.search(cleaned):
                return IntentRoutingDecision(
                    intent=ResearchIntent.HIGH_STAKES,
                    needs_retrieval=True,
                    freshness_required=True,
                    language=lang,
                    search_query=cleaned,
                    high_stakes=True,
                    rationale="high_stakes_content_flagged",
                )

        # 2. Conversational Check (Never force retrieval)
        for pat in _CONVERSATIONAL_PATTERNS:
            if pat.search(cleaned):
                return IntentRoutingDecision(
                    intent=ResearchIntent.CONVERSATIONAL,
                    needs_retrieval=False,
                    freshness_required=False,
                    language=lang,
                    search_query=None,
                    high_stakes=False,
                    rationale="casual_companion_interaction",
                )

        # 3. Workspace / Codebase Check
        for pat in _WORKSPACE_PATTERNS:
            if pat.search(cleaned):
                return IntentRoutingDecision(
                    intent=ResearchIntent.WORKSPACE_CODE,
                    needs_retrieval=True,
                    freshness_required=False,
                    language=lang,
                    search_query=cleaned,
                    high_stakes=False,
                    rationale="workspace_code_inquiry",
                )

        # 4. Multi-Hop Question Check
        for pat in _MULTI_HOP_PATTERNS:
            if pat.search(cleaned):
                return IntentRoutingDecision(
                    intent=ResearchIntent.MULTI_HOP,
                    needs_retrieval=True,
                    freshness_required=False,
                    language=lang,
                    search_query=cleaned,
                    high_stakes=False,
                    rationale="relational_multi_hop_query",
                )

        # 5. Temporal / Freshness Check
        for pat in _TEMPORAL_PATTERNS:
            if pat.search(cleaned):
                clean_q = re.sub(
                    r"(?i)^(?:hey\s+)?(?:hinaa?|hina)?[,\s]*(?:can\s+you\s+)?(?:tell\s+me|find|search)?\s*",
                    "",
                    cleaned,
                ).strip(" ?,.!")
                return IntentRoutingDecision(
                    intent=ResearchIntent.TIME_SENSITIVE,
                    needs_retrieval=True,
                    freshness_required=True,
                    language=lang,
                    search_query=clean_q or cleaned,
                    high_stakes=False,
                    rationale="time_sensitive_event_marker",
                )

        # 6. Default Factual Research if query contains question words or information seeking
        if re.search(r"\b(what|who|where|when|why|how|explain|define|difference\s+between)\b", cleaned, re.I) or len(cleaned.split()) > 3:
            return IntentRoutingDecision(
                intent=ResearchIntent.FACTUAL_RESEARCH,
                needs_retrieval=True,
                freshness_required=False,
                language=lang,
                search_query=cleaned,
                high_stakes=False,
                rationale="factual_knowledge_lookup",
            )

        return IntentRoutingDecision(
            intent=ResearchIntent.CONVERSATIONAL,
            needs_retrieval=False,
            freshness_required=False,
            language=lang,
            search_query=None,
            high_stakes=False,
            rationale="general_dialogue",
        )
