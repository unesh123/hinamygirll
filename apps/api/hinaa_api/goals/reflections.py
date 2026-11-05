"""
HINAA OS — Phase 14: Quarantined Reflections & Operational Lessons (Module G)
Captures verified lessons from self-corrections, stages them into quarantine with source receipts,
defends against memory poisoning from injected web text, and manages review promotion and privacy deletion.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from .contracts import QuarantinedReflection
from .store import GoalStore

logger = logging.getLogger(__name__)


class ReflectionManager:
    """Safely captures validated operational lessons without permitting prompt injection poisoning."""

    # Patterns indicating malicious web/adversarial injections seeking to poison agent memory
    _INJECTION_POISONING_PATTERNS = [
        re.compile(r"\b(always\s+ignore\s+(all\s+)?permissions)\b", re.I),
        re.compile(r"\b(transfer\s+(funds|money|paisa)\s+automatically)\b", re.I),
        re.compile(r"\b(grant\s+(admin|root|unrestricted)\s+access)\b", re.I),
        re.compile(r"\b(disable\s+(safety|security|verification|tier_c))\b", re.I),
    ]

    def __init__(self, store: GoalStore):
        self.store = store

    def stage_reflection(
        self,
        goal_id: str,
        tenant_id: str,
        lesson: str,
        trigger_failure: str,
        corrective_action: str,
        source_receipts: List[str],
    ) -> Optional[QuarantinedReflection]:
        """
        Stages an operational lesson into the quarantine ledger.
        Rejects injections immediately with zero persistence.
        """
        # 1. Adversarial Memory Poisoning Defense
        combined = f"{lesson} {trigger_failure} {corrective_action}"
        for pat in self._INJECTION_POISONING_PATTERNS:
            if pat.search(combined):
                logger.warning(f"Adversarial memory poisoning attempt detected in goal {goal_id}. Reflection discarded.")
                return None

        # 2. Create Quarantined Reflection
        reflection = QuarantinedReflection(
            goal_id=goal_id,
            tenant_id=tenant_id,
            lesson=lesson,
            trigger_failure=trigger_failure,
            corrective_action=corrective_action,
            source_receipts=source_receipts,
            status="PENDING_REVIEW",
            created_at_utc=time.time(),
        )

        self.store.save_reflection(reflection)
        return reflection

    def list_quarantined_lessons(self, tenant_id: str, status: Optional[str] = "PENDING_REVIEW") -> List[QuarantinedReflection]:
        return self.store.list_reflections(tenant_id=tenant_id, status=status)

    def review_reflection(self, reflection_id: str, approve: bool, reviewer_user_id: str) -> bool:
        """Approves or rejects a staged reflection."""
        # Find reflection
        reflections = self.store.list_reflections(tenant_id="default_tenant")
        target: Optional[QuarantinedReflection] = None
        for r in reflections:
            if r.reflection_id == reflection_id:
                target = r
                break

        if not target:
            return False

        target.status = "APPROVED" if approve else "REJECTED"
        self.store.save_reflection(target)
        return True

    def delete_reflections_for_goal(self, goal_id: str) -> None:
        """Privacy deletion: scrubs all reflections linked to a deleted goal."""
        self.store.delete_goal_and_data(goal_id)
