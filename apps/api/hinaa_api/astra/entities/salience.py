"""HINA ASTRA — Entity Salience & Attention Engine.

Maintains recency and prominence scores for tracked entities over multi-turn conversations.
"""

from __future__ import annotations

import math
from typing import Sequence

from .models import EntityState

# Default decay factor per turn without reference
DEFAULT_DECAY_RATE = 0.75
MIN_SALIENCE_THRESHOLD = 0.15


class SalienceTracker:
    """Manages salience transitions and attention decay for conversation entities."""

    def __init__(self, decay_rate: float = DEFAULT_DECAY_RATE) -> None:
        self.decay_rate = decay_rate

    def step_turn(self, entities: list[EntityState], current_turn: int) -> None:
        """Apply turn-based exponential decay to all entities not updated in the current turn."""
        for ent in entities:
            if ent.last_turn < current_turn:
                turns_elapsed = current_turn - ent.last_turn
                decay = math.pow(self.decay_rate, turns_elapsed)
                ent.salience = max(0.01, ent.salience * decay)

    def boost(self, entity: EntityState, current_turn: int, amount: float = 0.5) -> None:
        """Boost salience when an entity is explicitly mentioned or referenced."""
        entity.salience = min(1.0, entity.salience + amount)
        entity.last_turn = current_turn
        entity.mention_count += 1

    def active_focus(self, entities: Sequence[EntityState], top_k: int = 5) -> list[EntityState]:
        """Return the current foreground active entities sorted by salience and recency."""
        ranked = sorted(
            [e for e in entities if e.salience >= MIN_SALIENCE_THRESHOLD],
            key=lambda e: (e.salience, e.last_turn, e.mention_count),
            reverse=True,
        )
        return ranked[:top_k]
