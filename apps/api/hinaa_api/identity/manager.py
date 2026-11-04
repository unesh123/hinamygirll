"""Identity Manager coordinating character profile, persistence, and prompt framing."""

from __future__ import annotations

import time
import logging
from typing import Any
from hinaa_api.identity.models import CharacterIdentity, RelationshipMode, PersonaTraits
from hinaa_api.identity.store import IdentityStore
from hinaa_api.identity.anti_repetition import RepetitionDetector

logger = logging.getLogger("hinaa.identity.manager")


class IdentityManager:
    """Coordinates persistent identity, mode transitions, and anti-repetition filters."""

    def __init__(self, store: IdentityStore | None = None) -> None:
        self.store = store or IdentityStore()
        self.identity: CharacterIdentity = self.store.load()
        self.repetition_detector = RepetitionDetector()

    def set_relationship_mode(self, mode: RelationshipMode) -> None:
        """Transitions active relationship mode and updates persistence."""
        self.identity.active_mode = mode
        self.identity.last_updated = time.time()
        self.store.save(self.identity)
        logger.info("Identity relationship mode transitioned to: %s", mode.value)

    def update_traits(self, **kwargs: float) -> None:
        """Updates numeric persona traits with validation."""
        current_dict = self.identity.traits.model_dump()
        for k, v in kwargs.items():
            if k in current_dict:
                current_dict[k] = max(0.0, min(1.0, float(v)))
        self.identity.traits = PersonaTraits(**current_dict)
        self.identity.last_updated = time.time()
        self.store.save(self.identity)

    def increment_interaction(self) -> int:
        """Increments and saves interaction count."""
        self.identity.total_interactions += 1
        self.identity.last_updated = time.time()
        self.store.save(self.identity)
        return self.identity.total_interactions

    def filter_response(self, text: str) -> str:
        """Applies anti-repetition and anti-filler hygiene to outgoing response."""
        cleaned, _ = self.repetition_detector.sanitize(text)
        return cleaned

    def get_system_prompt_segment(self) -> str:
        """Generates dynamic identity injection prompt segment."""
        t = self.identity.traits
        mode = self.identity.active_mode.value
        
        mode_guidelines = {
            RelationshipMode.COMPANION: "Be warm, attentive, and conversational. Express sincere interest without canned sentimental filler.",
            RelationshipMode.CO_PILOT: "Act as an elite technical co-pilot. Offer structured architectural insight, proactive fixes, and clean code.",
            RelationshipMode.ANALYST: "Deliver concise, evidence-grounded analysis. Prioritize precision, citations, and critical evaluations.",
            RelationshipMode.AUTONOMOUS_OPERATOR: "Operate with self-directed initiative. Propose and execute bounded tasks with clear verification milestones.",
        }.get(self.identity.active_mode, "Provide competent, authentic assistance.")

        invariants_bulleted = "\n".join(f"- {inv}" for inv in self.identity.invariants)

        return (
            f"=== CHARACTER IDENTITY: {self.identity.name.upper()} ===\n"
            f"Archetype: {self.identity.core_archetype}\n"
            f"Active Mode: {mode.upper()} ({mode_guidelines})\n"
            f"Persona Calibration: Warmth={t.warmth:.2f}, Intellect={t.intellect:.2f}, "
            f"Playfulness={t.playfulness:.2f}, Technical Depth={t.technical_depth:.2f}\n"
            f"Core Invariants:\n{invariants_bulleted}\n"
            f"Rule: Never claim an action was done without verified tool execution. "
            f"Speak with genuine warmth and direct engagement. Do not use repetitive romantic loops."
        )


_global_identity_manager: IdentityManager | None = None


def get_identity_manager() -> IdentityManager:
    global _global_identity_manager
    if _global_identity_manager is None:
        _global_identity_manager = IdentityManager()
    return _global_identity_manager
