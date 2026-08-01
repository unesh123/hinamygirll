from __future__ import annotations

import re

from ..models import AssistantTurnPlan, CompanionId, Emotion, Language, Performance
from .models import ResponseDepth

EMOTION_ALLOWLIST = (
    "neutral",
    "happy",
    "excited",
    "playful",
    "shy",
    "concerned",
    "sad",
    "surprised",
    "thinking",
)
FACE_ALLOWLIST = (
    "neutral",
    "soft_smile",
    "big_smile",
    "blush",
    "pout",
    "concerned",
    "surprised",
    "thinking",
)
GESTURE_ALLOWLIST = (
    "none",
    "small_nod",
    "head_shake",
    "gentle_head_tilt",
    "wave",
    "explain",
    "celebrate",
    "reassure",
    "listening_lean",
)

PERFORMANCE_SCHEMA_LAYER = f"""ASSISTANT TURN PLAN CONTRACT:
- Return only values from approved allowlists.
- emotion.primary ∈ {list(EMOTION_ALLOWLIST)}
- performance.facePreset ∈ {list(FACE_ALLOWLIST)}
- performance.gesture ∈ {list(GESTURE_ALLOWLIST)}
- gazeTarget ∈ ["camera","away","down","user-content"]
- headMotion ∈ ["none","subtle","nod","shake"]
- blinkRate between 0.1 and 1.0
- memoryCandidates: empty unless the product later supplies explicit remember flow (currently prefer [])
- toolRequests: always []
- Never invent animation filenames, bone names, blendshapes, URLs, code, or tools.
- Prefer restrained intensity. At most one major gesture cue per turn.
- Serious, sensitive, uncertain, or error contexts: prefer neutral/thinking/concerned and avoid playful/celebrate.
- Do not diagnose the user's private emotional state; choose symbolic performance for the assistant's delivery only."""

_SERIOUS = re.compile(
    r"\b(error|bug|crash|fail|failed|exception|deadline|exam|anxious|anxiety|depress|"
    r"suicide|self[- ]?harm|abuse|grief|funeral|emergency|help me|problem|issue|"
    r"debug|stacktrace|production|outage)\b|"
    r"(समस्या|दुःख|चिन्ता|मद्दत|गलत|बिग्र)",
    re.IGNORECASE,
)
_CELEBRATE = re.compile(
    r"\b(thanks|thank you|great|awesome|solved|passed|done|finished|celebrate|yay)\b|"
    r"(धन्यवाद|भयो|सक्यो|राम्रो)",
    re.IGNORECASE,
)
_GREET = re.compile(
    r"\b(hi|hello|hey|namaste|good morning|good evening)\b|(नमस्ते|हेलो)",
    re.IGNORECASE,
)
_EXPLAIN = re.compile(
    r"\b(explain|how|why|what is|steps|guide|tutorial|assignment|code|implement)\b|"
    r"(कसरी|किन|के हो|बुझा|explain|assignment)",
    re.IGNORECASE,
)


def plan_performance(
    *,
    text: str,
    companion_id: CompanionId,
    depth: ResponseDepth,
    language: Language,
) -> tuple[Emotion, Performance]:
    """Deterministic allowlisted performance cues for live/mock planning."""
    serious = bool(_SERIOUS.search(text)) or depth in {"supportive", "safety_redirect"}
    celebrate = bool(_CELEBRATE.search(text)) and not serious
    greet = bool(_GREET.search(text)) and not serious
    explain = bool(_EXPLAIN.search(text)) or depth in {"explanatory", "procedural"}

    if serious:
        emotion = Emotion(primary="concerned", intensity=0.4, valence=-0.1, arousal=-0.05)
        performance = Performance(
            facePreset="concerned",
            gesture="reassure",
            gazeTarget="camera",
            headMotion="subtle",
            blinkRate=0.4,
        )
    elif celebrate:
        emotion = Emotion(primary="happy", intensity=0.55, valence=0.45, arousal=0.25)
        performance = Performance(
            facePreset="soft_smile" if companion_id == "hiro" else "big_smile",
            gesture="celebrate" if companion_id == "hinaa" else "small_nod",
            gazeTarget="camera",
            headMotion="nod",
            blinkRate=0.5,
        )
    elif greet:
        emotion = Emotion(
            primary="playful" if companion_id == "hinaa" else "happy",
            intensity=0.5,
            valence=0.4,
            arousal=0.2,
        )
        performance = Performance(
            facePreset="soft_smile",
            gesture="gentle_head_tilt" if companion_id == "hinaa" else "wave",
            gazeTarget="camera",
            headMotion="subtle",
            blinkRate=0.45,
        )
    elif explain:
        emotion = Emotion(primary="thinking", intensity=0.45, valence=0.1, arousal=0.05)
        performance = Performance(
            facePreset="thinking",
            gesture="explain",
            gazeTarget="camera",
            headMotion="subtle",
            blinkRate=0.42,
        )
    else:
        emotion = Emotion(primary="happy", intensity=0.42, valence=0.3, arousal=0.1)
        performance = Performance(
            facePreset="soft_smile",
            gesture="gentle_head_tilt" if companion_id == "hinaa" else "small_nod",
            gazeTarget="camera",
            headMotion="subtle",
            blinkRate=0.45,
        )
    return emotion, performance


def build_plan_from_text(
    *,
    text: str,
    companion_id: CompanionId,
    language: Language,
    depth: ResponseDepth,
) -> AssistantTurnPlan:
    spoken = text.strip()[:4000] or "I'm here. How can I help?"
    emotion, performance = plan_performance(
        text=spoken, companion_id=companion_id, depth=depth, language=language
    )
    return AssistantTurnPlan(
        spokenText=spoken,
        displayText=spoken[:8000],
        language=language,
        emotion=emotion,
        performance=performance,
        beats=[],
        memoryCandidates=[],
        toolRequests=[],
    )
