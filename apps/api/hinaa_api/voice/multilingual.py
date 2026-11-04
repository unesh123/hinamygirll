"""Multilingual Speech Normalizer & Code-Switching Engine for HINAA OS.

Provides phonetic normalization, script identification, and vocabulary
alignment across English, Nepali, Hindi, and cultural/developer terminology.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import NamedTuple


class LanguageClass(str, Enum):
    ENGLISH = "en"
    NEPALI = "ne"
    HINDI = "hi"
    MIXED_CODE_SWITCH = "mixed"


class PhoneticMatch(NamedTuple):
    pattern: re.Pattern[str]
    replacement: str
    target_lang: LanguageClass | None = None


# Unicode ranges for Devanagari script
_DEVANAGARI_RANGE = re.compile(r"[\u0900-\u097F]")

# Common phonetic mistranscriptions mapped to canonical tokens
_PHONETIC_CANONICAL_MAP: tuple[tuple[re.Pattern[str], str], ...] = (
    # ── 1. Anime / Isekai / Manga Terms ──
    (re.compile(r"\b(is[es]?[eai]k[ai]+|isecai|isikay|इसकाई|इसेकाई)\b", re.IGNORECASE), "Isekai"),
    (re.compile(r"\b(otaku|otacoo|ओटाकु|ओताकु)\b", re.IGNORECASE), "Otaku"),
    (re.compile(r"\b(sh[ou]+nen|shonun|शोनेन)\b", re.IGNORECASE), "Shonen"),
    (re.compile(r"\b(waifu|wayfu|वाइफू)\b", re.IGNORECASE), "Waifu"),
    (re.compile(r"\b(sakuga|sacuga|साकुगा)\b", re.IGNORECASE), "Sakuga"),
    (re.compile(r"\b(kawaii|kawai|कावाइ)\b", re.IGNORECASE), "Kawaii"),
    (re.compile(r"\b(tsundere|टुन्डरे)\b", re.IGNORECASE), "Tsundere"),

    # ── 2. Assistant & Character Identities ──
    (re.compile(r"\b(hinaa?|heena|hinna|हिना|हीना)\b", re.IGNORECASE), "Hinaa"),
    (re.compile(r"\b(hiro|heero|हिरो|हीरो)\b", re.IGNORECASE), "Hiro"),

    # ── 3. Developer & AI Frameworks ──
    (re.compile(r"\b(blue\s*stacks?|bluestax|ब्लुस्ट्याक्स)\b", re.IGNORECASE), "BlueStacks"),
    (re.compile(r"\b(fast\s*api|fast-api|फास्ट\s*एपिआई)\b", re.IGNORECASE), "FastAPI"),
    (re.compile(r"\b(type\s*script|टाइप\s*स्क्रिप्ट)\b", re.IGNORECASE), "TypeScript"),
    (re.compile(r"\b(q\s*lora|q-lora|cue\s*lora|क्यु\s*लोरा)\b", re.IGNORECASE), "QLoRA"),
    (re.compile(r"\b(lo\s*ra|laura|लोरा)\b", re.IGNORECASE), "LoRA"),
    (re.compile(r"\b(ol+ama|ओलामा)\b", re.IGNORECASE), "Ollama"),
    (re.compile(r"\b(py\s*torch|पाइटॉर्च)\b", re.IGNORECASE), "PyTorch"),
    (re.compile(r"\b(a\s*d\s*b|a-d-b|एडीबी)\b", re.IGNORECASE), "ADB"),
    (re.compile(r"\b(docker|डकर)\b", re.IGNORECASE), "Docker"),
    (re.compile(r"\b(github|गिटहब)\b", re.IGNORECASE), "GitHub"),

    # ── 4. Nepali Common Conversational Markers ──
    (re.compile(r"\b(sanchai\s+ch[ha]u|sanchai\s+chau)\b", re.IGNORECASE), "सञ्चै छौ"),
    (re.compile(r"\b(k\s+ch[ha]|k\s+cha)\b", re.IGNORECASE), "के छ"),
    (re.compile(r"\b(thik\s+ch[ha]|thik\s+cha)\b", re.IGNORECASE), "ठिक छ"),
    (re.compile(r"\b(dhanyaba+d|dhanybhad)\b", re.IGNORECASE), "धन्यवाद"),
    (re.compile(r"\b(timilai|timilai\s+kasto\s+cha)\b", re.IGNORECASE), "तिमीलाई"),

    # ── 5. Hindi Common Conversational Markers ──
    (re.compile(r"\b(kya\s+haal\s+hai|kya\s+hal\s+h)\b", re.IGNORECASE), "क्या हाल है"),
    (re.compile(r"\b(shukriya|shukreeya)\b", re.IGNORECASE), "शुक्रिया"),
    (re.compile(r"\b(theek\s+hai|thik\s+hai)\b", re.IGNORECASE), "ठीक है"),
)

# Pronunciation respelling for TTS speech synthesis
_TTS_PRONUNCIATION_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bHINAA\b", re.IGNORECASE), "Hee-nah"),
    (re.compile(r"\bHinaa\b"), "Hee-nah"),
    (re.compile(r"\bHiro\b"), "Hee-ro"),
    (re.compile(r"\bIsekai\b", re.IGNORECASE), "Ee-seh-kai"),
    (re.compile(r"\bFastAPI\b", re.IGNORECASE), "fast A P I"),
    (re.compile(r"\bTypeScript\b", re.IGNORECASE), "type script"),
    (re.compile(r"\bQLoRA\b", re.IGNORECASE), "Q-LoRA"),
    (re.compile(r"\bADB\b"), "A D B"),
    (re.compile(r"\bPyTorch\b", re.IGNORECASE), "Pie Torch"),
)


class MultilingualNormalizer:
    """Normalizes speech transcripts and adapts text for multilingual synthesis."""

    @classmethod
    def detect_dominant_language(cls, text: str) -> LanguageClass:
        """Classifies text into English, Nepali, Hindi, or Mixed Code-Switching."""
        if not text or not text.strip():
            return LanguageClass.ENGLISH

        devanagari_chars = len(_DEVANAGARI_RANGE.findall(text))
        total_chars = len(re.findall(r"\w", text))

        if total_chars == 0:
            return LanguageClass.ENGLISH

        devanagari_ratio = devanagari_chars / total_chars

        # Explicit Nepali grammatical markers (Indic-safe boundary)
        nepali_markers = re.compile(
            r"(?:^|[\s,.!?।])(छौ|छन्|गर्यो|हुनुहुन्छ|गर्नु|छ|हो|भयो|सञ्चै|तिमी|तिमीलाई|हामी|कस्तो|किन|भने)(?:$|[\s,.!?।])"
        )
        # Explicit Hindi grammatical markers (Indic-safe boundary)
        hindi_markers = re.compile(
            r"(?:^|[\s,.!?।])(है|हैं|था|थी|किया|होगा|सकते|क्या|कहाँ|हूँ|मुझे|आप|आपका|नमस्ते|अच्छा|हाल)(?:$|[\s,.!?।])"
        )

        nepali_hits = len(nepali_markers.findall(text))
        hindi_hits = len(hindi_markers.findall(text))

        if devanagari_ratio > 0.4:
            if nepali_hits > hindi_hits:
                return LanguageClass.NEPALI
            if hindi_hits > nepali_hits:
                return LanguageClass.HINDI
            if nepali_hits > 0 and hindi_hits > 0:
                return LanguageClass.MIXED_CODE_SWITCH
            return LanguageClass.NEPALI

        # Romanized code-switching detection
        roman_nepali = re.compile(r"\b(sanchai|k cha|thik cha|dhanyabad|timi|tapai|mero)\b", re.IGNORECASE)
        roman_hindi = re.compile(r"\b(kya haal|shukriya|kaise ho|namaste|theek hai|mera)\b", re.IGNORECASE)

        has_roman_ne = bool(roman_nepali.search(text))
        has_roman_hi = bool(roman_hindi.search(text))

        if has_roman_ne and not has_roman_hi:
            return LanguageClass.NEPALI
        if has_roman_hi and not has_roman_ne:
            return LanguageClass.HINDI
        if has_roman_ne and has_roman_hi:
            return LanguageClass.MIXED_CODE_SWITCH

        return LanguageClass.ENGLISH

    @classmethod
    def normalize_transcript(cls, text: str) -> str:
        """Corrects phonetic speech misrecognitions and standardizes key terminology."""
        if not text:
            return ""

        result = text
        for pattern, replacement in _PHONETIC_CANONICAL_MAP:
            result = pattern.sub(replacement, result)

        # Standardize extra spacing around punctuation
        result = re.sub(r"\s+([,.!?।])", r"\1", result)
        result = re.sub(r"\s{2,}", " ", result).strip()
        return result

    @classmethod
    def prepare_tts_pronunciation(cls, text: str) -> str:
        """Converts specialized technical & character tokens into phonetic representations for TTS."""
        if not text:
            return ""

        result = text
        for pattern, replacement in _TTS_PRONUNCIATION_RULES:
            result = pattern.sub(replacement, result)

        return result
