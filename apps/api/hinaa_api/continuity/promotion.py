from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..media.asset_store import get_asset_store
from ..persistence.orm import (
    ConversationEntity,
    EpisodicMemory,
    ExplicitMemory,
    UserContinuityState,
)
from .models import MemoryScope, MemoryWriteAction

logger = logging.getLogger("hinaa.continuity.promotion")

SENSITIVE_RE = re.compile(
    r"\b(password|api[_ ]?key|secret|token|ssn|credit card|bank account)\b",
    re.IGNORECASE,
)
NOISE_RE = re.compile(
    r"^(?:hey|hi|hello|what's up|good morning|thanks|thank you|ok|okay|yes|no|cool|bye)\b",
    re.IGNORECASE,
)


class MemoryWritePolicy:
    """Gating policy for memories to prevent indiscriminate database bloating."""

    @staticmethod
    def evaluate(content: str, *, context: dict[str, Any] | None = None) -> tuple[MemoryWriteAction, MemoryScope]:
        text = content.strip()
        if not text or len(text) < 3:
            return MemoryWriteAction.DISCARD, MemoryScope.CONVERSATION

        if SENSITIVE_RE.search(text):
            return MemoryWriteAction.DISCARD, MemoryScope.CONVERSATION

        lowered = text.lower()
        if NOISE_RE.match(lowered) and len(text.split()) <= 3:
            return MemoryWriteAction.DISCARD, MemoryScope.CONVERSATION

        # Check for character/entity approved asset or design instruction
        if any(w in lowered for w in ("approved face", "favorite reference", "always use this face", "always use this image", "official design")):
            return MemoryWriteAction.PROMOTE_GLOBAL, MemoryScope.USER_GLOBAL

        # Check for project architectural facts
        if any(w in lowered for w in ("uses postgres", "uses fastapi", "uses react", "stack is", "architecture is", "database is")):
            return MemoryWriteAction.KEEP_PROJECT, MemoryScope.PROJECT

        # Check for global procedural/format preferences
        if any(w in lowered for w in ("prefer concise", "keep final summary", "short summary", "always run tests", "for full documents")):
            return MemoryWriteAction.KEEP_PROCEDURAL, MemoryScope.USER_GLOBAL

        # Check for persistent personal facts
        if any(w in lowered for w in ("i like", "i prefer", "my name is", "call me", "i live in", "i work as")):
            return MemoryWriteAction.KEEP_SEMANTIC, MemoryScope.USER_GLOBAL

        # Default episodic event
        return MemoryWriteAction.KEEP_EPISODIC, MemoryScope.CONVERSATION


class MemoryPromotionService:
    """Promotes transient conversation observations into durable cross-session continuity."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def promote_approved_asset(
        self,
        owner_id: str,
        *,
        entity_name: str,
        asset_id: str,
        conversation_id: str | None = None,
        description: str = "",
    ) -> None:
        """Promote an asset as the approved reference of a character or project."""
        asset_store = get_asset_store()
        asset_store.register_asset_metadata(
            asset_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            entity_ids=[entity_name],
            approval_state="approved",
            tags=["approved_reference", entity_name.lower()],
            semantic_metadata={"entity": entity_name, "description": description},
        )

        with self._factory() as session:
            # Update or create UserContinuityState
            state = session.scalar(select(UserContinuityState).where(UserContinuityState.owner_id == owner_id))
            if not state:
                state = UserContinuityState(owner_id=owner_id)
                session.add(state)
                session.flush()

            import json
            approved_list = []
            try:
                approved_list = json.loads(state.approved_asset_ids_json)
            except Exception:
                pass
            if asset_id not in approved_list:
                approved_list.append(asset_id)
                state.approved_asset_ids_json = json.dumps(approved_list)

            # Update important entities
            entities = []
            try:
                entities = json.loads(state.important_entities_json)
            except Exception:
                pass

            norm_name = entity_name.strip().lower()
            matched = False
            for ent in entities:
                if ent.get("name", "").lower() == norm_name:
                    ent["approved_face"] = asset_id
                    ent["approved_reference"] = asset_id
                    matched = True
                    break
            if not matched:
                entities.append({
                    "name": entity_name,
                    "normalized": norm_name,
                    "approved_face": asset_id,
                    "approved_reference": asset_id,
                })
            state.important_entities_json = json.dumps(entities)
            state.memory_revision += 1
            state.last_interaction_at = datetime.now(UTC)

            # Add explicit memory record
            content_text = f"{entity_name} approved face reference is {asset_id}"
            import hashlib
            digest = hashlib.sha256(content_text.lower().encode("utf-8")).hexdigest()
            mem = ExplicitMemory(
                user_id=owner_id,
                content=content_text,
                normalized_hash=digest,
                category="preference",
                scope="user_global",
                entity_id=entity_name,
                status="approved",
                consent_state="explicit",
                source_turn_ref=f"convo:{conversation_id}" if conversation_id else None,
            )
            session.add(mem)

            # Record episodic event (ensuring Conversation exists for foreign key)
            from ..persistence.orm import Conversation
            cid = conversation_id or "global"
            convo = session.get(Conversation, cid)
            if not convo:
                convo = Conversation(id=cid, user_id=owner_id, companion_id="hinaa")
                session.add(convo)
                session.flush()

            event = EpisodicMemory(
                user_id=owner_id,
                conversation_id=cid,
                event=f"Approved asset {asset_id} as reference for {entity_name}",
                event_type="asset_approved",
                importance=4,
                scope="user_global",
            )
            session.add(event)
            session.commit()
            logger.info("Promoted asset %s as approved reference for %s (owner=%s)", asset_id, entity_name, owner_id)

    def handle_user_correction(
        self,
        owner_id: str,
        *,
        entity_name: str | None,
        attribute: str,
        new_value: str,
        old_value_hint: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        """Supersede previous attribute facts and establish the corrected state."""
        with self._factory() as session:
            # Look for active memories touching this attribute
            mems = session.scalars(
                select(ExplicitMemory)
                .where(
                    ExplicitMemory.user_id == owner_id,
                    ExplicitMemory.status == "approved",
                    ExplicitMemory.deleted_at.is_(None),
                )
            ).all()

            import hashlib
            new_content = f"{entity_name or 'character'} {attribute} is {new_value}"
            new_digest = hashlib.sha256(new_content.lower().encode("utf-8")).hexdigest()

            new_mem = ExplicitMemory(
                user_id=owner_id,
                content=new_content,
                normalized_hash=new_digest,
                category="correction",
                scope="user_global",
                entity_id=entity_name,
                status="approved",
                consent_state="explicit",
                source_turn_ref=f"convo:{conversation_id}" if conversation_id else None,
            )
            session.add(new_mem)
            session.flush()

            # Supersede matching old memories
            for old in mems:
                if attribute.lower() in old.content.lower():
                    if not entity_name or entity_name.lower() in old.content.lower():
                        old.status = "superseded"
                        old.superseded_by_id = new_mem.id
                        logger.info("Superseded old memory '%s' with '%s'", old.content, new_content)

            # Record episodic audit trail (ensuring Conversation exists for foreign key)
            from ..persistence.orm import Conversation
            cid = conversation_id or "global"
            convo = session.get(Conversation, cid)
            if not convo:
                convo = Conversation(id=cid, user_id=owner_id, companion_id="hinaa")
                session.add(convo)
                session.flush()

            event = EpisodicMemory(
                user_id=owner_id,
                conversation_id=cid,
                event=f"Corrected {entity_name or 'character'} {attribute} to {new_value}",
                event_type="attribute_corrected",
                importance=3,
                scope="user_global",
            )
            session.add(event)
            session.commit()
