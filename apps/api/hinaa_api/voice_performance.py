from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

VoiceMode = Literal[
    "neutral",
    "warm",
    "bright",
    "calm",
    "professional",
    "celebratory",
    "thoughtful",
    "apologetic",
]


class VoicePerformancePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: VoiceMode = "neutral"
    pace: Annotated[float, Field(ge=0.85, le=1.15)] = 1.0
    pitch_semitones: Annotated[float, Field(ge=-2.0, le=2.0)] = 0.0
    volume: Annotated[float, Field(ge=0.75, le=1.0)] = 1.0
    warmth: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5
    energy: Annotated[float, Field(ge=0.0, le=1.0)] = 0.45


# Provider/product names (gemini, azure) are deliberately NOT tech-task
# signals: saying "gemini ai assistant made by google" or "azure" must not
# flatten her into the professional (flat, robotic) delivery — that is exactly
# the "she stops being herself when I mention AI" complaint. Only genuine
# coding/task words flip the delivery.
_TECH = re.compile(
    r"\b(code|bug|api|error|debug|typescript|fastapi|websocket|sql|http)\b",
    re.IGNORECASE,
)
_SERIOUS = re.compile(
    r"\b(sorry|error|fail|problem|issue|frustrat|anxious|help)\b|"
    r"(माफ|समस्या|गलत)",
    re.IGNORECASE,
)
_CELEBRATE = re.compile(r"\b(great|awesome|done|passed|thanks|धन्यवाद|भयो)\b", re.IGNORECASE)
_GREET = re.compile(r"\b(hi|hello|hey|namaste|नमस्ते)\b", re.IGNORECASE)


# The same ranges the blocked-reply rule strips, so the two places that take emoji
# out of what she says do not disagree about what an emoji is.
_EMOJI_CLASS = r"\U0001F300-\U0001FAFF☀-➿️"

# Speech-only substitutions; display text remains unchanged.
PRONUNCIATION_MAP = (
    (re.compile(r"\bHINAA\b"), "Hee-nah"),
    (re.compile(r"\bHinaa\b"), "Hee-nah"),
    (re.compile(r"\bHiro\b"), "Hee-ro"),
    (re.compile(r"\bWebSocket\b"), "web socket"),
    (re.compile(r"\bFastAPI\b"), "fast A P I"),
    (re.compile(r"\bTypeScript\b"), "type script"),
    (re.compile(r"\bGemini\b"), "jem-in-eye"),
    (re.compile(r"\bAzure\b"), "azh-ure"),
)


def plan_voice_performance(*, user_text: str, reply_text: str, depth: str) -> VoicePerformancePlan:
    text = f"{user_text}\n{reply_text}"
    if depth in {"supportive", "safety_redirect"} or _SERIOUS.search(text):
        return VoicePerformancePlan(
            mode="calm" if "sorry" not in text.lower() else "apologetic",
            pace=0.94,
            pitch_semitones=-0.4,
            volume=0.9,
            warmth=0.75,
            energy=0.3,
        )
    if _TECH.search(text) or depth in {"procedural", "explanatory", "report"}:
        return VoicePerformancePlan(
            mode="professional",
            pace=0.98,
            pitch_semitones=0.0,
            volume=1.0,
            warmth=0.4,
            energy=0.4,
        )
    if _CELEBRATE.search(text):
        return VoicePerformancePlan(
            mode="celebratory",
            pace=1.06,
            pitch_semitones=0.8,
            volume=1.0,
            warmth=0.75,
            energy=0.7,
        )
    if _GREET.search(text):
        return VoicePerformancePlan(
            mode="bright",
            pace=1.04,
            pitch_semitones=0.5,
            volume=1.0,
            warmth=0.7,
            energy=0.6,
        )
    if depth == "thoughtful" or "thinking" in reply_text.lower():
        return VoicePerformancePlan(
            mode="thoughtful",
            pace=0.96,
            pitch_semitones=-0.2,
            volume=0.95,
            warmth=0.6,
            energy=0.35,
        )
    return VoicePerformancePlan(mode="warm", pace=1.0, pitch_semitones=0.2, warmth=0.7, energy=0.5)


# The pet name is an address term, so the comma that introduced it goes with
# it; dropping the word alone would leave "later,. Love you" for the voice.
# बाबु/जानू are the same address terms in Devanagari, and ए/अरे is the
# vocative in front of them: a measured Nepali turn opened with "ए बाबु,"
# because only the Latin spellings were stripped.
#
# The two scripts cannot share one boundary rule. Devanagari vowel signs are
# non-word characters to re, so \b fires inside बाबु and a \b-anchored
# Devanagari term matches nothing; those are bounded by the script block
# instead, which also keeps बाबुराज and जान ("life") as content.
#
# बाबे/बेबी are the Latin terms written the way a Nepali turn says them. A
# live turn opened with "अरे बाबे," because the -े and -ी spellings were not
# in the list; the boundary still leaves a glued form like बाबेको alone.
_PET_NAME = (
    r"(?:\b(?:babes?|baby|babu|jaanu)\b"
    r"|(?<![\u0900-\u097F])(?:बाबु|बाबू|बाबे|जानू|बेबी|बेब|प्रिय)(?![\u0900-\u097F]))"
)
# The interjection in front of the term is Roman-script in a Hinglish reply, so
# the Devanagari-only list left "Arey" behind on a measured live turn. बेब is
# that same Latin term written in Devanagari, which a Hindi live turn opened with.
_VOCATIVE = r"(?:(?:अरे|ए|ओ|arey|arre|are|o)\s+)?"
_ADDRESS_TERM = rf"{_VOCATIVE}{_PET_NAME}"


_GREETING = r"(?:(?:नमस्ते|नमस्कार|namaste|namaskar|hello|hey|hi)\s+)?"

# The live turn after that opened with "अरे मेरे " in a delta of its own. Unlike a
# pet name, मेरे is also the ordinary possessive "my" -- मेरे पास means "I have" --
# so it may only go when the chunk proves it was used as an address: standing
# alone, or carrying its own pause. A rule that matched it anywhere would delete
# content from the middle of his answer.
_OPENING_SALUTATION = re.compile(
    r"^(?:अरे\s+)?मेरे(?:[ \t]*[,.!?]+[ \t]*|[ \t]*$)",
    re.IGNORECASE,
)

# The turn after that opened with a bare interjection in a chunk of its own, with
# no pet name left to anchor on. Only a chunk that is nothing but the interjection
# can go, because that is the one case with no content to lose: "are" and single
# letters are also how a stream splits a real word mid-reply.
_BARE_INTERJECTION = re.compile(
    r"^(?:अरे|arey|arre)[ \t]*[,.!?]*[ \t]*$",
    re.IGNORECASE,
)


def strip_greeting(text: str) -> str:
    """Remove the greeting she is told to open a reply with.

    Measured openings were "Arey babe, ", then "अरे बेब, ", then "नमस्ते बेब!":
    a salutation in front of the term and an exclamation behind it, so an
    anchored, comma-only rule matched nothing the second time. The term still
    has to stand off from what follows with its own pause, so a word that merely
    begins with it ("Babel", "बेबसाइट") is content and stays.

    A voice turn arrives in chunks, so this runs on each one and never looks
    back: a term the stream split in two stays on screen exactly as she wrote
    it rather than being guessed at.

    The rule is deliberately narrower than the one the audio uses. Because this
    runs on every delta, a term that merely begins with one ("Babel") or is only
    followed by another word ("baby monitor") is content here, and newlines go
    nowhere -- paragraph breaks are what he reads on screen.
    """
    # Her opening takes its own punctuation with it, so "नमस्ते बेब! आज..." does
    # not leave a stray "!" on screen. Whatever blank line the greeting sits
    # behind is a paragraph break, so it comes back.
    if _BARE_INTERJECTION.match(text):
        return ""
    text = _OPENING_SALUTATION.sub("", text, count=1)
    stripped = re.sub(
        rf"^(\s*)(?:{_GREETING}{_VOCATIVE}{_PET_NAME})[ \t]*[,.!?]*[ \t]*",
        r"\1",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    # The full stop in "I set it at six, babe." ends the sentence, not the
    # address, so it stays: the match stops before it.
    stripped = re.sub(
        rf",[ \t]*(?:{_GREETING}{_VOCATIVE}{_PET_NAME})(?=[ \t]*[.!?)(,][ \t]*|[ \t]*$)",
        "",
        stripped,
        flags=re.IGNORECASE,
    )
    return re.sub(r"[ \t]{2,}", " ", stripped)


def speech_text_for_tts(display_text: str) -> str:
    spoken = display_text
    # 1. Strip XML/HTML tags like <spokenText>, </spokenText>, <displayText>, <think>
    spoken = re.sub(
        r"</?(?:spokenText|displayText|think|thought|content|message)[^>]*>",
        "",
        spoken,
        flags=re.IGNORECASE,
    )
    spoken = re.sub(r"<[^>]+>", " ", spoken)
    # 2. Strip trailing parenthetical parameter dumps like (affection=0.75, sass=0.35...)
    spoken = re.sub(
        r"\s*\([a-zA-Z_]+=[0-9.]+(?:,\s*[a-zA-Z_]+=[0-9.]+)*\)\s*$",
        "",
        spoken,
    )
    # 3. Strip code blocks and backticks
    spoken = re.sub(r"```[\s\S]*?```", " ", spoken)
    spoken = re.sub(r"`[^`]*`", " ", spoken)
    # 4. Pronunciation map substitutions
    for pattern, replacement in PRONUNCIATION_MAP:
        spoken = pattern.sub(replacement, spoken)
    # 5. Strip markdown formatting chars
    spoken = re.sub(r"[`*#_>~|]+", " ", spoken)
    # 6. Decoration the voice has to speak around. A TTS engine reads 🔥 as "fire",
    #    and the pet name the on-screen persona is told to use lands in nearly
    #    every sentence, which is what makes a spoken turn sound like the chat
    #    model reading itself aloud. Both stay in displayText: this function
    #    shapes the channel, not the reply.
    spoken = re.sub(rf"[{_EMOJI_CLASS}]", " ", spoken)
    # The pet name is an address term, so the comma that introduced it goes with
    # it; dropping the word alone would leave "later,. Love you" for the voice.
    # बाबु/जानू are the same address terms in Devanagari, and ए/अरे is the
    # vocative in front of them: a measured Nepali turn opened with "ए बाबु,"
    # because only the Latin spellings were stripped.
    #
    # The two scripts cannot share one boundary rule. Devanagari vowel signs are
    # non-word characters to re, so \b fires inside बाबु and a \b-anchored
    # Devanagari term matches nothing; those are bounded by the script block
    # instead, which also keeps बाबुराज and जान ("life") as content.
    #
    # बाबे/बेबी are the Latin terms written the way a Nepali turn says them. A
    # live turn opened with "अरे बाबे," because the -े and -ी spellings were not
    # in the list; the boundary still leaves a glued form like बाबेको alone.
    spoken = re.sub(rf",\s*{_ADDRESS_TERM}(?=[\s,.!]|$)", "", spoken, flags=re.IGNORECASE)
    spoken = re.sub(rf"\s*{_ADDRESS_TERM}\s*[,.!]?\s*", " ", spoken, flags=re.IGNORECASE)
    # A Markdown table's separator row is made of characters step 5 does not
    # recognise as formatting, so it survives as ":---:---:" and the voice reads it
    # out. A line of nothing but dashes, colons and pipes carries no content in
    # either channel. A content line keeps its letters and is untouched.
    spoken = re.sub(r"(?m)^[ \t]*(?:[-:|][ \t]*)+[ \t]*$", " ", spoken)
    # A bracketed source index points at a card on his screen. Spoken, it is a
    # bare number in the middle of a sentence with nothing to refer to.
    spoken = re.sub(r"\[\^?\d{1,3}(?:\s*[,;]\s*\^?\d{1,3})*\]", "", spoken)
    # Removing the decoration strands whatever leaned on it. Only the spaces and
    # the punctuation a removal created go -- a sentence keeps its own full stop.
    spoken = re.sub(r"\s+([,.;:!?])", r"\1", spoken)
    spoken = re.sub(r"\s+", " ", spoken).strip()
    return spoken


ALLOWED_SSML_TAGS = frozenset({"speak", "prosody", "break"})


def build_bounded_ssml(text: str, plan: VoicePerformancePlan) -> str:
    safe = (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
    rate = f"{plan.pace * 100:.0f}%"
    pitch = f"{plan.pitch_semitones:+.1f}st"
    volume = f"{plan.volume * 100:.0f}%"
    return (
        f'<speak version="1.0" xml:lang="hi-IN">'
        f'<prosody rate="{rate}" pitch="{pitch}" volume="{volume}">{safe}</prosody>'
        f"</speak>"
    )
