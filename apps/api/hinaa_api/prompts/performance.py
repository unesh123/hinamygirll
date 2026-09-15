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
- memoryCandidates: If the user reveals personal facts, preferences, name, location, interests, work context, or recurring patterns, emit them as memoryCandidates with {{"content": "...", "category": "fact|preference|workflow|task|conversation"}}. Keep entries concise (under 80 chars). Do NOT emit secrets, passwords, or API keys.
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
    explain = bool(_EXPLAIN.search(text)) or depth in {"explanatory", "procedural", "report"}

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


_INTRO_FILLER_PATTERN = re.compile(
    r"^(?:here(?:'s|\s+is|\s+are)\b.*?(?:breakdown|report|overview|details|summary|guide|analysis|plan|look|information|briefing)|"
    r"sure(?: thing)?[,!.\s]|certainly[,!.\s]|of course[,!.\s]|absolutely[,!.\s]|"
    r"alright[,!.\s]|all right[,!.\s]|gladly[,!.\s]|i'd be glad\b|let's dive\b|let's explore\b|"
    r"(?:hey|hello|hi)\b.*?[,!.]|"
    r"(?:babe|love|sweetheart|darling)[,!.\s]|"
    r"(?:यहाँ|नमस्ते|हेर|हेरौँ|म यहाँ|यो रिपोर्टमा|विस्तृत विवरण)(?:\s+|$|[!,।.-]))",
    re.IGNORECASE,
)

_SUMMARY_HEADER_PATTERN = re.compile(
    r"(?:^|\n)#{1,4}\s*(?:executive\s+summary|summary|overview|key\s+takeaways?|tl;?dr)[^\n]*\n([\s\S]*?)(?=\n#{1,4}|\Z)",
    re.IGNORECASE,
)


def _clean_for_speech(raw: str) -> str:
    plain = re.sub(r"```[\s\S]*?```", " ", raw)
    plain = re.sub(r"^\s{0,3}#{1,6}\s+.*$", " ", plain, flags=re.MULTILINE)
    plain = re.sub(r"^\s*[-*_]{3,}\s*$", " ", plain, flags=re.MULTILINE)
    plain = re.sub(r"^\s*[-*+]\s+", " ", plain, flags=re.MULTILINE)
    plain = re.sub(r"^\s*\|.*\|\s*$", " ", plain, flags=re.MULTILINE)
    plain = re.sub(r"(?i)\*?\s*as of [^\n*]+\*?", " ", plain)
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
    plain = re.sub(r"\[\d+(?:,\s*\d+)*\]", " ", plain)
    plain = plain.replace("`", "").replace("**", "").replace("__", "")
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain


def extract_executive_voice_summary(text: str, limit: int = 150) -> str:
    """Extract a high-signal, substantive executive summary (< limit chars)
    suitable for TTS, skipping conversational filler and introductory waffle."""
    if not text or not text.strip():
        return "I'm here. How can I help?"

    match = _SUMMARY_HEADER_PATTERN.search(text)
    candidate_text = match.group(1) if match else text

    plain = _clean_for_speech(candidate_text)
    if not plain and match:
        plain = _clean_for_speech(text)

    if not plain:
        return text[:limit].strip() or "I'm here. How can I help?"

    sentences = [piece.strip() for piece in re.split(r"(?<=[.!?।])\s+", plain) if piece.strip()]
    substantive_sentences: list[str] = []

    for s in sentences:
        if s.endswith(":") or len(s.split()) < 3:
            continue
        if _INTRO_FILLER_PATTERN.search(s) and len(s.split()) <= 10:
            continue
        substantive_sentences.append(s)

    if not substantive_sentences:
        substantive_sentences = [s for s in sentences if not s.endswith(":") and len(s.split()) >= 3]

    if not substantive_sentences:
        candidate = plain[:limit].strip()
        if candidate and not re.search(r"[.!?।]\s*$", candidate):
            candidate = candidate.rsplit(" ", 1)[0] + "…"
        return candidate or "I've placed the details in chat for you."

    collected: list[str] = []
    curr_len = 0
    for s in substantive_sentences:
        added_len = len(s) + (1 if collected else 0)
        if curr_len + added_len <= limit:
            collected.append(s)
            curr_len += added_len
        else:
            if not collected:
                collected.append(s)
            break

    spoken = " ".join(collected)

    if len(spoken) > limit:
        window = spoken[:limit]
        last_punct = max(window.rfind("."), window.rfind("!"), window.rfind("?"), window.rfind("।"))
        if last_punct >= int(limit * 0.45):
            spoken = window[:last_punct + 1].strip()
        else:
            last_space = window.rfind(" ")
            spoken = (window[:last_space] if last_space != -1 else window).rstrip(" ,;—") + "…"

    return spoken


def build_plan_from_text(
    *,
    text: str,
    companion_id: CompanionId,
    language: Language,
    depth: ResponseDepth,
) -> AssistantTurnPlan:
    valid_langs = {"en-US", "hi-IN", "ne-NP", "mixed"}
    lang_map = {"en": "en-US", "hi": "hi-IN", "ne": "ne-NP", "english": "en-US", "hindi": "hi-IN", "nepali": "ne-NP"}
    resolved_lang: Language = lang_map.get(str(language).lower(), language if language in valid_langs else "mixed")  # type: ignore[assignment]
    cleaned = re.sub(
        r"</?(?:spokenText|displayText|think|thought|content|message)[^>]*>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*\([a-zA-Z_]+=[0-9.]+(?:,\s*[a-zA-Z_]+=[0-9.]+)*\)\s*$",
        "",
        cleaned,
    )
    display_full = cleaned.strip() or "I'm here. How can I help?"
    # Spoken text is an executive summary (< 150 chars) conveying the substantive core finding
    spoken = extract_executive_voice_summary(display_full, limit=150)
    emotion, performance = plan_performance(
        text=spoken, companion_id=companion_id, depth=depth, language=resolved_lang
    )
    return AssistantTurnPlan(
        spokenText=spoken,
        displayText=display_full,
        language=resolved_lang,
        emotion=emotion,
        performance=performance,
        beats=[],
        memoryCandidates=[],
        toolRequests=[],
    )
