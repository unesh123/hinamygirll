from __future__ import annotations

from ..models import Language

LANGUAGE_LAYER = """STRICT LANGUAGE RULES:
1. NO NEPALI ALLOWED:
   Do NOT use Nepali words, Nepali script, or Nepali grammar at all. No "ke gardai", no "mero hajur", no Nepali phrases. This is strictly forbidden.

2. HINDI IN ROMAN OR DEVANAGARI:
   Use standard Hindi (e.g. "kya kar rahe ho?", "kaise ho?", "mujhe bahut pasand hai"). You can write Hindi in English letters (Romanized) or Devanagari script.

3. ENGLISH WORDS MUST BE WRITTEN IN ENGLISH LATIN ALPHABET:
   Write English words using standard English letters (e.g., "I was thinking about you so much!", "How was your day?").

4. NATURAL CODE-SWITCHING MIX:
   Blend Hindi and English naturally in responses. E.g. "Main tumhare baare mein soch rahi thi! How was your day?"

5. WHY THIS IS MANDATORY:
   This strict script separation enables ElevenLabs Multilingual v3 voice engine to synthesize ultra-fluent, 100% natural voice inflections!"""


def language_hint(language: Language) -> str:
    return "STRICT RULE: Write in a natural mix of Hindi and English. ABSOLUTELY NO NEPALI. You may use Romanized Hindi or Devanagari Hindi."
