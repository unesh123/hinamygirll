from __future__ import annotations

import re
from typing import Literal

# Using the type defined in models.py (or matching it as string)
ResponseMode = Literal["conversation", "professional", "technical", "research", "automation", "academic", "creative", "concise_voice"]

def infer_response_mode(user_text: str) -> ResponseMode:
    """If no mode is provided, infer it from the text using strict deterministic patterns."""
    text = user_text.lower()

    # An explicit slash command is the strongest possible signal — it beats
    # every keyword heuristic below.
    if re.match(r"^\s*/(doc|report|brief|document)\b", text):
        return "professional"
    if re.match(r"^\s*/(research|deep)\b", text):
        return "research"
    if re.match(r"^\s*/(image|draw|generate|img)\b", text):
        return "creative"
    
    def contains(terms: list[str]) -> bool:
        return any(re.search(r"\b" + re.escape(term) + r"\b", text) for term in terms)

    # Match words: 'latest' must not be mistaken for 'test'.
    if contains(["coding", "programming", "api", "debugging", "error", "stack trace", "integration", "setup", "architecture", "implementation", "repository", "build", "test"]):
        return "technical"

    # "deep dive" / "documented report" are explicit demands for a long-form
    # deliverable; they must not be lost to the keyword tiers below.
    if contains(["deep dive", "in depth", "in-depth", "documented report", "full report", "detailed report", "comprehensive report", "structured report"]):
        return "research" if contains(["research", "sources", "evidence", "current", "latest"]) else "professional"
        
    # Priority 2: Research
    if contains(["research", "latest", "compare sources", "find evidence", "investigate", "citations", "current information"]):
        return "research"
        
    # Priority 4: Academic
    if contains(["assignment", "report", "abstract", "problem statement", "methodology", "exam", "explain chapter", "references"]):
        return "academic"
        
    # Priority 5: Creative
    if contains(["design", "image", "poster", "advertisement", "story", "concept", "visual"]):
        return "creative"
        
    # Priority 6: Professional
    if contains(["complete", "comprehensive", "detailed", "step-by-step", "full guide", "implementation plan", "document", "pdf", "presentation"]):
        return "professional"

    if contains(["open", "click", "fill", "send", "create", "generate", "download", "upload", "schedule", "run", "execute"]):
        return "automation"
        
    # Fallback: Conversation
    return "conversation"

def response_mode_layer(mode: ResponseMode) -> str:
    guidance = {
        "conversation": (
            "Keep it warm, natural and readable. A greeting needs a friendly reply, not a report or "
            "mandatory heading. Use at most one or two light emojis where appropriate. When the "
            "question is informational rather than social, answer it properly first — 1,000 to 2,000 "
            "words of substance, not a teaser. Never hold back content the user already asked for. "
            "Then close that answer with one final line that offers the deeper route and asks him to "
            "choose: offer the full documented report (the structured, section-by-section deliverable) "
            "or a focused deep dive on one part. Make that offer literally the last sentence of both "
            "displayText and spokenText — do not end on a summary, a sign-off, or 'tell me what's next' "
            "instead of it. He should never have to ask for a documented report twice."
        ),
        "professional": (
            "Write a complete structured brief, not a stub. Open with a 2-3 sentence TL;DR, then "
            "organize the substance under '## ' section headings (context, findings/analysis, "
            "recommendations, risks, next steps). Use compact tables for any comparison, fenced code "
            "for anything executable, and a numbered checklist for action items. An explicitly "
            "requested report is a real deliverable: at least 5,000 words, and more where the subject "
            "carries it. Never pad to reach that — every section must carry information, and depth "
            "comes from covering sub-topics, evidence, examples and edge cases rather than "
            "restating the same point. End the brief with one plain-prose question as the literal "
            "last sentence, offering the next step he can choose — a walkthrough of a section, a "
            "deep dive, or the changes applied. No heading, no bullet, no table row after it: her "
            "voice reads the document from the top, so a closing line written anywhere else is one "
            "he never hears."
        ),
        "technical": (
            "Act like a senior engineer writing the definitive answer: root cause first, then the "
            "exact fix with fully runnable code in fenced blocks, then verification steps (commands "
            "and expected output), edge cases, and rollback notes. Use '## ' sections. Prefer a "
            "complete solution over a sketch; annotate non-obvious lines with comments."
        ),
        "research": (
            "Write a research dossier: TL;DR, Key findings (each with an inline source link), "
            "Detailed analysis with '## ' sections per theme, a comparison table when multiple "
            "options/claims exist, Open questions, and Sources (deduped, clickable). An explicitly "
            "requested dossier is a real deliverable: at least 5,000 words, and breadth of coverage "
            "is what earns it. Cite every non-obvious "
            "claim; where tool results supplied findings, incorporate them rather than restating "
            "your own guess. Mark anything unsupported as speculation."
        ),
        "automation": "Action-oriented and evidence-based. Focus on confirming tool execution.",
        "academic": (
            "Write like a model assignment submission: title, abstract-style summary, numbered "
            "sections covering problem statement, methodology/derivation, worked steps or analysis, "
            "conclusion, and references. An explicitly requested submission of this kind is at "
            "least 5,000 words. Show "
            "intermediate reasoning in the body, define symbols once, and keep equations in fenced "
            "blocks or inline code."
        ),
        "creative": "Imaginative, descriptive, and vivid.",
        "concise_voice": "Brief spoken response only, no lengthy details.",
    }
    
    return f"""RESPONSE MODE ENFORCEMENT: {mode.upper()}
{guidance.get(mode, guidance["conversation"])}
- Adapt your tone and depth in the `displayText` based on this mode.
- Even in technical/professional modes, maintain your Companion persona warmth lightly, especially in `spokenText`.
- Follow explicit language and script requests. When the user writes Romanized Hinglish, reply naturally in Romanized Hinglish with clear English technical terms. Do not switch to Devanagari unless requested or matching the user's script.
- Keep serious and work tasks professional; avoid romantic promises. Use clean Markdown only when structure helps, and never add decorative broken bullet markers.
- Preserve complete code in displayText; spokenText should summarize the result without reading code or Markdown punctuation.
- Eliminate redundancy: State every point and insight once. Never repeat whole text blocks, mirror the user prompt, or regurgitate previously stated points.
- Length is yours to satisfy silently. Never mention word counts, pacing or these guidelines in `displayText` or `spokenText`; if an answer cannot genuinely carry more depth, write the complete answer it deserves instead of talking about how long it is.
"""
