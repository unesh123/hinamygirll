"""
HINAA OS — Delivery Intent and Mode Router (Module A)
Disambiguates user intent across English, Devanagari Nepali, Romanized Nepali,
and code-mixed inputs to select the optimal DeliveryMode, audience level, and language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from .contracts import DeliveryMode


# Unicode range for Devanagari script
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

# Common Romanized Nepali markers
_ROMANIZED_NEPALI_TOKENS = {
    "bujhaideu", "bujhau", "bhana", "padha", "garaun", "chha", "ho", "kina",
    "kasari", "thorey", "purai", "ferari", "arko", "aru", "sikaideu", "bistrit",
    "jastako", "tastai", "malai", "timi", "kura", "kasto", "pani"
}


@dataclass(slots=True)
class RouteResult:
    delivery_mode: DeliveryMode
    language: str              # "en", "ne", "mixed"
    audience_level: str        # "general", "beginner", "technical", "executive"
    confidence: float          # 0.0 - 1.0
    reason: str
    target_section: Optional[str] = None
    time_budget_seconds: float = 30.0


class IntentDeliveryRouter:
    """Routes dialogue turns and artifact requests to an authoritative DeliveryMode."""

    # 1. READ_VERBATIM patterns (MUST be strictly evaluated to disambiguate from explanations)
    _VERBATIM_PATTERNS = [
        re.compile(r"\b(read\s+(this\s+)?word\s+for\s+word|read\s+verbatim|narrate\s+exactly|read\s+out\s+loud\s+exactly)\b", re.I),
        re.compile(r"\b(don'?t\s+summarize[,.\s]+read\s+(the\s+)?(document|report|text))\b", re.I),
        re.compile(r"\b(जस्ताको\s*तस्तै\s*पढ|अक्षरशः\s*पढ|शब्द[- ]शब्द\s*पढ|परिवर्तन\s*नगरी\s*पढ)\b"),
        re.compile(r"\b(jastako\s*tastai\s*padha|exact\s*padha|verbatim\s*padha|word\s*for\s*word\s*padha)\b", re.I),
    ]

    # 2. EXPLAIN_DIFFERENTLY patterns
    _DIFFERENTLY_PATTERNS = [
        re.compile(r"\b(explain\s+(it\s+)?differently|another\s+way|say\s+it\s+differently|different\s+(angle|perspective|analogy|framing))\b", re.I),
        re.compile(r"\b(tell\s+me\s+in\s+another\s+way|rephrase\s+with\s+an\s+analogy)\b", re.I),
        re.compile(r"\b(अर्को\s*तरिकाले\s*बुझाऊ|फरक\s*तरिकाले\s*भन|अरू\s*उदाहरण\s*दिएर\s*भन)\b"),
        re.compile(r"\b(aru\s*tarika\s*le\s*bujhau|arka\s*tarika\s*le\s*bujhau|faraka\s*tarika\s*le|arko\s*example\s*deu)\b", re.I),
    ]

    # 3. PERSPECTIVE_AND_CRITIQUE patterns
    _CRITIQUE_PATTERNS = [
        re.compile(r"\b(critique|tradeoffs?|counterarguments?|what\s+are\s+the\s+risks|another\s+perspective|weigh\s+the\s+pros\s+and\s+cons|limitations?)\b", re.I),
        re.compile(r"\b(फाइदा\s*बेफाइदा|जोखिम|आलोचना|कमी\s*कमजोरी|पक्ष\s*विपक्ष)\b"),
        re.compile(r"\b(tradeoff|risk|alochanatmak|fayda\s*befayda|kamjori)\b", re.I),
    ]

    # 4. TEACH_STEP_BY_STEP patterns
    _TEACH_PATTERNS = [
        re.compile(r"\b(teach\s+me|step\s+by\s+step|how\s+does\s+it\s+work\s+step\s+by\s+step|walk\s+me\s+through\s+slowly)\b", re.I),
        re.compile(r"\b(i\s+don'?t\s+understand\s+section\s*(\d+|\w+)|explain\s+section\s*(\d+|\w+))\b", re.I),
        re.compile(r"\b(सिकाइदेऊ|चरणबद्ध\s*रूपमा|मलाई\s*यो\s*बुझ्न\s*मद्दत\s*गर)\b"),
        re.compile(r"\b(sikaideu|step\s*by\s*step\s*sikaideu|bujhina|bujhna\s*sakina)\b", re.I),
    ]

    # 5. EXPLAIN_FULLY patterns
    _FULLY_PATTERNS = [
        re.compile(r"\b(explain\s+in\s+detail|detailed\s+walkthrough|walk\s+me\s+through|section\s+by\s+section|full\s+explanation|deep\s+dive|go\s+deeper)\b", re.I),
        re.compile(r"\b(विस्तारमा\s*भन|विस्तृतमा\s*बुझाइदेऊ|सबै\s*व्याख्या\s*गर|गहिराइमा\s*भन)\b"),
        re.compile(r"\b(bistar\s*ma\s*bhana|bistritma\s*bujhaideu|detail\s*ma\s*bhana|purai\s*bujhau|deep\s*dive)\b", re.I),
    ]

    # 6. DISCUSS patterns
    _DISCUSS_PATTERNS = [
        re.compile(r"\b(let'?s\s+discuss|what\s+do\s+you\s+think|discuss\s+this|talk\s+about\s+it)\b", re.I),
        re.compile(r"\b(छलफल\s*गरौँ|यसबारे\s*कुरा\s*गरौँ|तिम्रो\s*विचार\s*के\s*छ)\b"),
        re.compile(r"\b(chhalfal\s*garaun|kura\s*garaun|timro\s*bichar\s*k\s*chha)\b", re.I),
    ]

    # 7. EXPLAIN_BRIEFLY patterns
    _BRIEF_PATTERNS = [
        re.compile(r"\b(briefly|short\s+summary|give\s+me\s+the\s+gist|quick\s+briefing|in\s+short|main\s+points|key\s+takeaways?|explain\s+(this|the)\s+(report|document))\b", re.I),
        re.compile(r"\b(छोटोमा\s*बुझाइदेऊ|छोटोमा\s*भन|सार\s*के\s*हो|संक्षेपमा\s*भन|थोरैमा\s*व्याख्या\s*गर)\b"),
        re.compile(r"\b(chhotoma\s*bujhaideu|chhotoma\s*bhana|gist\s*bhana|thorey\s*ma\s*bhana|quick\s*ma\s*bhana)\b", re.I),
    ]

    def route(
        self,
        user_text: str,
        artifact_present: bool = False,
        default_mode: DeliveryMode = DeliveryMode.EXPLAIN_BRIEFLY,
    ) -> RouteResult:
        """Determines the delivery mode, target language, and audience level from user prompt."""
        text = user_text.strip()
        lang = self.detect_language(text)
        audience = self.detect_audience(text)

        # Check section targeting: e.g. "I don't understand section 2"
        section_match = re.search(r"section\s*(\d+|\w+)", text, re.I)
        target_section = f"Section {section_match.group(1)}" if section_match else None

        # 1. Explicit READ_VERBATIM check
        for pat in self._VERBATIM_PATTERNS:
            if pat.search(text):
                return RouteResult(
                    delivery_mode=DeliveryMode.READ_VERBATIM,
                    language=lang,
                    audience_level=audience,
                    confidence=0.98,
                    reason="Explicit request for word-for-word verbatim reading",
                    target_section=target_section,
                    time_budget_seconds=180.0,
                )

        # 2. EXPLAIN_DIFFERENTLY
        for pat in self._DIFFERENTLY_PATTERNS:
            if pat.search(text):
                return RouteResult(
                    delivery_mode=DeliveryMode.EXPLAIN_DIFFERENTLY,
                    language=lang,
                    audience_level=audience,
                    confidence=0.95,
                    reason="Request for a different framing, analogy, or perspective",
                    target_section=target_section,
                    time_budget_seconds=40.0,
                )

        # 3. PERSPECTIVE_AND_CRITIQUE
        for pat in self._CRITIQUE_PATTERNS:
            if pat.search(text):
                return RouteResult(
                    delivery_mode=DeliveryMode.PERSPECTIVE_AND_CRITIQUE,
                    language=lang,
                    audience_level=audience,
                    confidence=0.92,
                    reason="Request for critique, tradeoffs, implications, or risks",
                    target_section=target_section,
                    time_budget_seconds=45.0,
                )

        # 4. TEACH_STEP_BY_STEP
        for pat in self._TEACH_PATTERNS:
            if pat.search(text):
                return RouteResult(
                    delivery_mode=DeliveryMode.TEACH_STEP_BY_STEP,
                    language=lang,
                    audience_level=audience,
                    confidence=0.90,
                    reason="Request for step-by-step teaching or section clarification",
                    target_section=target_section,
                    time_budget_seconds=60.0,
                )

        # 5. EXPLAIN_FULLY
        for pat in self._FULLY_PATTERNS:
            if pat.search(text):
                return RouteResult(
                    delivery_mode=DeliveryMode.EXPLAIN_FULLY,
                    language=lang,
                    audience_level=audience,
                    confidence=0.92,
                    reason="Request for comprehensive section-by-section walkthrough",
                    target_section=target_section,
                    time_budget_seconds=90.0,
                )

        # 6. DISCUSS
        for pat in self._DISCUSS_PATTERNS:
            if pat.search(text):
                return RouteResult(
                    delivery_mode=DeliveryMode.DISCUSS,
                    language=lang,
                    audience_level=audience,
                    confidence=0.88,
                    reason="Request for interactive two-way discussion",
                    target_section=target_section,
                    time_budget_seconds=30.0,
                )

        # 7. EXPLAIN_BRIEFLY
        for pat in self._BRIEF_PATTERNS:
            if pat.search(text):
                return RouteResult(
                    delivery_mode=DeliveryMode.EXPLAIN_BRIEFLY,
                    language=lang,
                    audience_level=audience,
                    confidence=0.90,
                    reason="Request for short, high-level briefing of main takeaways",
                    target_section=target_section,
                    time_budget_seconds=30.0,
                )

        # Default fallback:
        # If an artifact is present, default to EXPLAIN_BRIEFLY so Hina speaks a concise conversational
        # briefing rather than reading the entire document aloud.
        if artifact_present:
            return RouteResult(
                delivery_mode=default_mode,
                language=lang,
                audience_level=audience,
                confidence=0.80,
                reason="Default conversational briefing for newly created or active artifact",
                target_section=target_section,
                time_budget_seconds=30.0,
            )

        # Standard voice chat
        return RouteResult(
            delivery_mode=DeliveryMode.VOICE_CHAT,
            language=lang,
            audience_level=audience,
            confidence=0.75,
            reason="Standard conversational dialogue turn",
            target_section=target_section,
            time_budget_seconds=25.0,
        )

    @classmethod
    def detect_language(cls, text: str) -> str:
        """Determines if text is Nepali (Devanagari), Romanized Nepali, English, or Code-mixed."""
        has_devanagari = bool(_DEVANAGARI_RE.search(text))
        lower_words = set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))
        has_romanized = bool(lower_words & _ROMANIZED_NEPALI_TOKENS)

        if has_devanagari and len(lower_words) > 3:
            return "mixed"
        if has_devanagari:
            return "ne"
        if has_romanized:
            # Romanized Nepali code-mixed with English terms
            return "mixed" if len(lower_words - _ROMANIZED_NEPALI_TOKENS) > 2 else "ne"
        return "en"

    @classmethod
    def detect_audience(cls, text: str) -> str:
        """Extracts desired audience level from phrasing."""
        lower = text.lower()
        if any(term in lower for term in ["like i'm 5", "eli5", "beginner", "simple words", "for kids", "layman"]):
            return "beginner"
        if any(term in lower for term in ["executive", "leadership", "c-level", "high level", "for manager", "business impact"]):
            return "executive"
        if any(term in lower for term in ["technical", "under the hood", "engineering", "architecture", "implementation", "code level"]):
            return "technical"
        return "general"
