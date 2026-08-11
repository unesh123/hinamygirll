from __future__ import annotations

from typing import Literal

# Using the type defined in models.py (or matching it as string)
ResponseMode = Literal["conversation", "professional", "technical", "research", "automation", "academic", "creative", "concise_voice"]

def infer_response_mode(user_text: str) -> ResponseMode:
    """If no mode is provided, infer it from the text using strict deterministic patterns."""
    text = user_text.lower()
    
    # Priority 1: Technical
    if any(w in text for w in ["coding", "programming", "api", "debugging", "error", "stack trace", "integration", "setup", "architecture", "implementation", "repository", "build", "test"]):
        return "technical"
        
    # Priority 2: Research
    if any(w in text for w in ["research", "latest", "compare sources", "find evidence", "investigate", "citations", "current information"]):
        return "research"
        
    # Priority 3: Automation
    if any(w in text for w in ["open", "click", "fill", "send", "create", "generate", "download", "upload", "schedule", "run", "execute"]):
        return "automation"
        
    # Priority 4: Academic
    if any(w in text for w in ["assignment", "report", "abstract", "problem statement", "methodology", "exam", "explain chapter", "references"]):
        return "academic"
        
    # Priority 5: Creative
    if any(w in text for w in ["design", "image", "poster", "advertisement", "story", "concept", "visual"]):
        return "creative"
        
    # Priority 6: Professional
    if any(w in text for w in ["complete", "comprehensive", "detailed", "step-by-step", "full guide", "implementation plan", "document everything"]):
        return "professional"
        
    # Fallback: Conversation
    return "conversation"

def response_mode_layer(mode: ResponseMode) -> str:
    guidance = {
        "conversation": "Keep it warm and conversational. Standard depth.",
        "professional": "Detailed, formal, and structured. exhaustive depth.",
        "technical": "Provide step-by-step troubleshooting, code, and exact steps. Deep depth.",
        "research": "Neutral, sourced, and structured with citations. Deep depth.",
        "automation": "Action-oriented and evidence-based. Focus on confirming tool execution.",
        "academic": "Scholarly, structured, focused on learning. Deep depth.",
        "creative": "Imaginative, descriptive, and vivid.",
        "concise_voice": "Brief spoken response only, no lengthy details.",
    }
    
    return f"""RESPONSE MODE ENFORCEMENT: {mode.upper()}
{guidance.get(mode, guidance["conversation"])}
- Adapt your tone and depth in the `displayText` based on this mode.
- Even in technical/professional modes, maintain your Companion persona warmth lightly, especially in `spokenText`.
"""
