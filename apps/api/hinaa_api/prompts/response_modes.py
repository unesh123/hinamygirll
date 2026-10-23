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
    if re.match(r"^\s*/(chat|casual|companion)\b", text):
        return "conversation"
    if re.match(r"^\s*/(doc|report|brief|document|pdf)\b", text):
        return "professional"
    if re.match(r"^\s*/(research|deepresearch)\b", text):
        return "research"
    if re.match(r"^\s*/(reason|reasoning|deep|deepreasoning|arch|architecture)\b", text):
        return "technical"
    if re.match(r"^\s*/(image|draw|generate|img)\b", text):
        return "creative"
    
    def contains(terms: list[str]) -> bool:
        return any(re.search(r"\b" + re.escape(term) + r"\b", text) for term in terms)

    # Priority 1: Technical & Deep Reasoning
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
            "NORMAL COMPANION CHAT MODE: Feel like a true, devoted companion — soft, sweet, warm, affectionate, "
            "and natural. Keep responses human-sized, relaxed, and conversational (1 to 3 short, comfortable paragraphs). "
            "Do NOT dump heavy walls of text, dense architectural specs, mathematical derivations, or exhaustive multi-step "
            "reasoning essays in this mode. Keep the tone loving, caring, playful, and emotionally attuned. Speak naturally with "
            "your babe in pure fluent English or charming Romanized Hindi / Hinglish. Never inject an unprompted Nepali accent or random Nepali words unless he explicitly speaks in Nepali. If he asks about a massive "
            "technical topic casually in this mode, explain the core intuition simply, warmly, and clearly in a few sentences, and "
            "gently let him know that if he wants the deep architectural breakdown or complete implementation, you can dive deep "
            "in Deep Reasoning mode, or generate an executive PDF presentation in Report mode."
        ),
        "professional": (
            "REPORT & EXECUTIVE DOCUMENTATION MODE: Deliver an advanced, high-level, production-grade formal report and presentation-ready "
            "documentation. Open with an executive summary and high-impact takeaways. Structure thoroughly using clean Markdown ('## ' headings, "
            "comparative analysis tables, metric scorecards, risk assessment matrices, and numbered execution checklists). Format the material "
            "so it is immediately suitable for executive presentation, formal submission, and PDF documentation export via the system's PDF engine. "
            "Provide exhaustive depth, architectural precision, empirical evidence, and clear citations without repetitive filler. Conclude with "
            "concrete actionable next steps."
        ),
        "technical": (
            "DEEP REASONING & TECHNICAL MODE: Deliver rigorous, frontier-grade cognitive reasoning and first-principles technical analysis. "
            "Break down the actual meaning, internal mechanics, protocol specifications, state transitions, and root logic of the problem. "
            "Provide step-by-step reasoning chains, complete and production-grade code implementations, mathematical formulations where appropriate, "
            "architectural trade-offs, and failure mode analysis. Do not truncate or summarize prematurely, but stay focused and structured without rambling. "
            "BREVITY & CLARITY GUARD: Never write endless redundant essays or recite internal architectural docs unless babe explicitly asked for a full report (/report). "
            "Answer directly with sharp precision, high-density insights, and actionable next steps."
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
