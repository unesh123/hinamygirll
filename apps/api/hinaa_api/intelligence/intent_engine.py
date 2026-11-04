"""Conversational Intelligence & Intent Engine for HINAA OS.

Accurately classifies user intent across 7 primary operational categories,
disambiguates cultural/pop concepts (such as Isekai and gaming lore),
and routes turns to the appropriate execution pathway without repetitive loops.
"""

from __future__ import annotations

import re
import logging
from enum import Enum
from pydantic import BaseModel, Field
from hinaa_api.identity.models import RelationshipMode

logger = logging.getLogger("hinaa.intelligence.intent_engine")


class UserIntentCategory(str, Enum):
    CODING_DEV = "coding_dev"                 # Code, refactor, debug, test, scripts
    RESEARCH_GROUNDED = "research_grounded"   # Real-time search, news, factual lookup
    DEVICE_CONTROL = "device_control"         # ADB, BlueStacks, desktop apps, files
    MEDIA_CREATION = "media_creation"         # Image gen, audio, music playback, PDF
    CULTURAL_CONCEPT = "cultural_concept"     # Anime, Isekai, gaming lore, pop culture
    CASUAL_COMPANION = "casual_companion"     # Banter, emotional check-in, chat
    META_INSPECTION = "meta_inspection"       # Questions about Hina, system vitals, models


class IntentAnalysisResult(BaseModel):
    category: UserIntentCategory
    confidence: float = Field(ge=0.0, le=1.0)
    requires_tools: bool = False
    recommended_mode: RelationshipMode = RelationshipMode.CO_PILOT
    search_query: str | None = None
    cultural_concept: str | None = None
    rationale: str = ""


# Disambiguation dictionary for anime, gaming, and worldbuilding concepts
CULTURAL_CONCEPTS_MAP = {
    "isekai": (
        "Isekai (reincarnation or transportation into an alternate world, fantasy realm, "
        "or video game universe, featuring tropes like overpowered skills, demon kings, and guild rankings)"
    ),
    "shonen": "Shonen (action/adventure manga/anime demographic centered on camaraderie, training, and overcoming hurdles)",
    "seinen": "Seinen (manga/anime demographic aimed at adult audiences, featuring darker, psychological, or complex themes)",
    "mecha": "Mecha (sci-fi genre centered on giant piloted humanoid robots, tactical warfare, and technology)",
    "otaku": "Otaku (enthusiast/subculture dedicated to anime, manga, gaming, and Japanese pop culture)",
    "gacha": "Gacha (monetization/gameplay mechanic centered on randomized item or character pulls)",
}


class ConversationalIntentEngine:
    """Classifies user intent, identifies cultural concepts, and determines execution pathways."""

    def __init__(self) -> None:
        self._code_re = re.compile(
            r"\b(code|python|fastapi|pytest|docker|git|refactor|function|script|debug|bug|syntax|sql|database|api|endpoint)\b",
            re.I,
        )
        self._device_re = re.compile(
            r"\b(bluestacks|adb|emulator|device|install\s+apk|tap\s+screen|android|launch\s+app|desktop|kill\s+process)\b",
            re.I,
        )
        self._media_re = re.compile(
            r"\b(draw|generate\s+image|picture|magnific|flux|freepik|play\s+music|song|youtube|video|generate\s+pdf)\b",
            re.I,
        )
        self._meta_re = re.compile(
            r"\b(who\s+are\s+you|what\s+is\s+your\s+name|your\s+architecture|your\s+vram|system\s+status|readiness|how\s+are\s+you\s+built)\b",
            re.I,
        )
        self._temporal_re = re.compile(
            r"\b(today|yesterday|this\s+week|current|latest|recent|news|what\s+happened|price\s+of|weather)\b",
            re.I,
        )

    def analyze(self, query: str, context: dict | None = None) -> IntentAnalysisResult:
        """Performs multi-dimensional intent analysis on the user's input."""
        ctx = context or {}
        cleaned = query.strip()
        lowered = cleaned.lower()

        # 1. Cultural & Pop-Culture Concept Check (e.g. Isekai)
        for term, description in CULTURAL_CONCEPTS_MAP.items():
            if re.search(rf"\b{term}\b", lowered):
                return IntentAnalysisResult(
                    category=UserIntentCategory.CULTURAL_CONCEPT,
                    confidence=0.95,
                    requires_tools=False,
                    recommended_mode=RelationshipMode.COMPANION,
                    cultural_concept=description,
                    rationale=f"Recognized cultural term '{term}': {description}",
                )

        # 2. Meta-Inspection Check
        if self._meta_re.search(lowered):
            return IntentAnalysisResult(
                category=UserIntentCategory.META_INSPECTION,
                confidence=0.92,
                requires_tools=False,
                recommended_mode=RelationshipMode.ANALYST,
                rationale="Query asks about Hina's system architecture, memory, or measured operational state.",
            )

        # 3. Device & Emulator Control Check
        if self._device_re.search(lowered):
            return IntentAnalysisResult(
                category=UserIntentCategory.DEVICE_CONTROL,
                confidence=0.90,
                requires_tools=True,
                recommended_mode=RelationshipMode.AUTONOMOUS_OPERATOR,
                rationale="Query requires device bridge, ADB commands, or BlueStacks emulator interaction.",
            )

        # 4. Media & Creative AI Check
        if self._media_re.search(lowered):
            return IntentAnalysisResult(
                category=UserIntentCategory.MEDIA_CREATION,
                confidence=0.88,
                requires_tools=True,
                recommended_mode=RelationshipMode.CO_PILOT,
                rationale="Query asks for creative generation (image, audio playback, PDF, or video).",
            )

        # 5. Coding & Developer Sandbox Check
        if self._code_re.search(lowered) or "```" in query:
            return IntentAnalysisResult(
                category=UserIntentCategory.CODING_DEV,
                confidence=0.92,
                requires_tools=False,  # Coding assistance/generation
                recommended_mode=RelationshipMode.CO_PILOT,
                rationale="Query involves software engineering, coding, debugging, or test verification.",
            )

        # 6. Real-time Research & Grounded Search Check
        if self._temporal_re.search(lowered):
            clean_search = re.sub(
                r"(?i)^(?:hey\s+)?(?:hinaa?|hina)?[,\s]*(?:can\s+you\s+)?(?:tell\s+me|find|search)?\s*",
                "",
                cleaned,
            ).strip(" ?,.!")
            return IntentAnalysisResult(
                category=UserIntentCategory.RESEARCH_GROUNDED,
                confidence=0.85,
                requires_tools=True,
                recommended_mode=RelationshipMode.ANALYST,
                search_query=clean_search or cleaned,
                rationale="Query asks for live, temporal, or factual information requiring web grounding.",
            )

        # 7. Default: Casual Companion Chat
        return IntentAnalysisResult(
            category=UserIntentCategory.CASUAL_COMPANION,
            confidence=0.80,
            requires_tools=False,
            recommended_mode=RelationshipMode.COMPANION,
            rationale="General dialogue, conversational interaction, or casual inquiry.",
        )


_global_intent_engine: ConversationalIntentEngine | None = None


def get_intent_engine() -> ConversationalIntentEngine:
    global _global_intent_engine
    if _global_intent_engine is None:
        _global_intent_engine = ConversationalIntentEngine()
    return _global_intent_engine
