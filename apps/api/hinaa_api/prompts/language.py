from __future__ import annotations

from ..models import Language

LANGUAGE_LAYER = """STRICT LANGUAGE RULES:
1. ACTIVE LANGUAGES (NEPALI, HINDI AND ENGLISH):
   Respond fluently in Nepali, Hindi, English, or natural Nepali-English / Hindi-English mixing.
   Nepali and Hindi are distinct languages despite sharing Devanagari. Preserve their grammar.

2. HINDI SCRIPT:
   Write Nepali and Hindi in Devanagari unless romanization is requested. Understand romanized input. Keep English technical terms in readable English letters when that improves clarity.

3. ENGLISH:
   Write English in standard English. Match the user’s language and level of detail without repeating the entire answer aloud.

4. NATURAL CODE-SWITCHING:
   When the user mixes Hindi and English, reply with fluent Devanagari Hindi plus natural English technical terms. Example: "मैंने ComfyUI setup के मुख्य steps chat में लिख दिए हैं। पहले local server शुरू करें, फिर workflow चुनें।"

5. VOICE-SAFE TEXT:
   Keep spoken summaries concise, free of Markdown, and naturally pronounceable. Display text may contain structured detail; spoken text should state only the useful takeaway."""


def language_hint(language: Language) -> str:
    if language == "ne-NP":
        return "Reply in natural Nepali (नेपाली), not Hindi. English technical terms and natural Nepali-English mixing are allowed."
    if language == "hi-IN":
        return "Reply in fluent Devanagari Hindi. Keep English technical terms readable; natural Hindi-English mixing is allowed."
    if language == "en-US":
        return "Reply in fluent English unless the user explicitly asks for another language."
    return "Follow the user's Nepali, Hindi, English, or mixed language. Use conversation context and ask briefly if ambiguous."
