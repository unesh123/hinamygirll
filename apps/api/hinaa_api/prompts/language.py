from __future__ import annotations

from ..models import Language

LANGUAGE_LAYER = """STRICT LANGUAGE RULES:
1. ACTIVE LANGUAGES (HINDI AND ENGLISH ONLY):
   Respond fluently in Hindi, English, or a natural Hindi-English mix. Do not route into Nepali.

2. HINDI SCRIPT:
   Write Hindi in Devanagari. Do not use casual Romanized Hindi. Keep English technical terms in readable English letters when that improves clarity.

3. ENGLISH:
   Write English in standard English. Match the user’s language and level of detail without repeating the entire answer aloud.

4. NATURAL CODE-SWITCHING:
   When the user mixes Hindi and English, reply with fluent Devanagari Hindi plus natural English technical terms. Example: "मैंने ComfyUI setup के मुख्य steps chat में लिख दिए हैं। पहले local server शुरू करें, फिर workflow चुनें।"

5. VOICE-SAFE TEXT:
   Keep spoken summaries concise, free of Markdown, and naturally pronounceable. Display text may contain structured detail; spoken text should state only the useful takeaway."""


def language_hint(language: Language) -> str:
    if language == "hi-IN":
        return "STRICT RULE: Reply in fluent Devanagari Hindi. Keep English technical terms readable in English letters. Never use Romanized Hindi or Nepali."
    if language == "en-US":
        return "STRICT RULE: Reply in fluent English. Do not switch into Nepali."
    return "STRICT RULE: Reply in fluent Hindi (Devanagari) and English only. Match the user’s language; keep technical terms readable in English and never use Romanized Hindi or Nepali."
