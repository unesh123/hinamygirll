"""
Proactive Briefing & Semantic Knowledge Engine for HINAA.

Generates proactive, time-aware, context-rich morning and work briefings
synthesizing recent topics, learned facts, and active goals.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_time_of_day_context() -> Dict[str, str]:
    now = datetime.datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        return {"period": "morning", "greeting": "Good morning", "vibe": "fresh and energized"}
    elif 12 <= hour < 17:
        return {"period": "afternoon", "greeting": "Good afternoon", "vibe": "focused and productive"}
    elif 17 <= hour < 22:
        return {"period": "evening", "greeting": "Good evening", "vibe": "relaxing and reviewing"}
    else:
        return {"period": "late_night", "greeting": "Hey night owl", "vibe": "quiet and deep-thinking"}


async def generate_proactive_briefing(
    user_id: str,
    memory_service: Any,
    companion_id: str = "hinaa",
) -> Dict[str, Any]:
    """Compile a personalized proactive briefing for the companion dashboard."""
    tod = _get_time_of_day_context()
    
    # 1. Fetch recent conversations to understand active projects
    recent_convos: List[Dict[str, Any]] = []
    try:
        if hasattr(memory_service, "list_conversations"):
            recent_convos = memory_service.list_conversations(user_id, limit=5)
    except Exception as err:
        logger.debug("Failed to fetch conversations for briefing: %s", err)

    # 2. Extract recent themes
    recent_topics: List[str] = []
    for c in recent_convos:
        title = c.get("title") or ""
        if title and title != "New conversation" and title not in recent_topics:
            recent_topics.append(title)

    # 3. Fetch learned user facts / preferences
    learned_facts: List[str] = []
    try:
        if hasattr(memory_service, "list_explicit_memories"):
            mems = memory_service.list_explicit_memories(user_id)
            learned_facts = [m.get("content", "") for m in mems if m.get("content")][:5]
    except Exception as err:
        logger.debug("Failed to fetch memories for briefing: %s", err)

    # 4. Formulate contextual greeting text
    period_greeting = tod["greeting"]
    topic_mention = ""
    if recent_topics:
        latest = recent_topics[0]
        topic_mention = f" I see we were recently diving into **{latest}**."

    greeting_msg = (
        f"{period_greeting}, Unesh! 🥰 Hinaa here, ready to co-pilot with you.{topic_mention} "
        f"All systems, 1M+ context models, and creative tools are primed and running smoothly. "
        f"What shall we create or solve right now?"
    )

    # 5. Smart contextual suggested actions
    suggestions = [
        {
            "id": "screen_copilot",
            "title": "Turn on Live Eyes",
            "subtitle": "Share your screen or camera for live code & UI review",
            "prompt": "Look at my screen and give me real-time feedback on what I'm working on.",
        },
        {
            "id": "deep_research_bundle",
            "title": "Autonomous Research Swarm",
            "subtitle": "Deep-dive any topic into an academic PDF & presentation",
            "prompt": "Perform deep research on advanced multi-agent architectures and generate a publication-grade PDF dossier.",
        },
        {
            "id": "creative_studio",
            "title": "Seedance 5.0 Visual Studio",
            "subtitle": "High-fidelity photorealistic and anime generation",
            "prompt": "Create a breathtaking visual illustration of an anime cyberpunk heroine overlooking a futuristic neon city in rain.",
        },
    ]

    return {
        "status": "success",
        "greeting": greeting_msg,
        "timeOfDay": tod["period"],
        "companionId": companion_id,
        "recentTopics": recent_topics[:4],
        "learnedFactsCount": len(learned_facts),
        "suggestions": suggestions,
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
