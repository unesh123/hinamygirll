from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..media.asset_store import get_asset_store
from ..persistence.orm import (
    Conversation,
    ConversationEntity,
    ConversationSummary,
    DurableTask,
    EpisodicMemory,
    Message,
    MessageAttachment,
    UserContinuityState,
)
from .models import ConversationSummaryData

logger = logging.getLogger("hinaa.continuity.finalizer")


class ConversationFinalizer:
    """Consolidates conversation events, updates summaries, and refreshes UserContinuityState."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def finalize_conversation(
        self,
        owner_id: str,
        conversation_id: str,
        *,
        force_summary: bool = False,
    ) -> ConversationSummaryData:
        """Process turn/conversation events into structured summary and update global state."""
        with self._factory() as session:
            # 1. Fetch conversation and messages
            convo = session.scalar(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == owner_id,
                )
            )
            if not convo:
                return ConversationSummaryData(conversation_id=conversation_id)

            messages = session.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.deleted_at.is_(None),
                )
                .order_by(Message.created_at.asc())
            ).all()

            if not messages:
                return ConversationSummaryData(conversation_id=conversation_id)

            # 2. Extract topics, entities, and decisions from message text
            user_texts = [m.content for m in messages if m.role == "user" and m.content]
            all_text = " ".join(user_texts)

            # Extract potential topics (significant capitalized words or phrases)
            topics = []
            stopwords = {"what", "where", "when", "why", "how", "this", "that", "there", "generate", "image", "hello", "hina", "please"}
            for word in re.findall(r"\b[A-Z][a-zA-Z0-9_-]+\b", all_text):
                if word.lower() not in stopwords and word not in topics:
                    topics.append(word)

            # Also check for phrases like "Kung Fu Panda", "Project Nova"
            for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", all_text):
                phrase = match.group(1)
                if phrase not in topics:
                    topics.insert(0, phrase)

            # 3. Collect conversation entities
            entities = session.scalars(
                select(ConversationEntity)
                .where(
                    ConversationEntity.conversation_id == conversation_id,
                    ConversationEntity.user_id == owner_id,
                )
            ).all()
            entity_dicts = [
                {"name": e.display_name, "type": e.entity_type, "asset_id": e.asset_id}
                for e in entities
            ]

            # 4. Collect attachments
            attachments = session.scalars(
                select(MessageAttachment)
                .join(Message, MessageAttachment.message_id == Message.id)
                .where(Message.conversation_id == conversation_id)
            ).all()
            asset_dicts = [
                {"asset_id": a.asset_id, "kind": a.kind, "filename": a.filename}
                for a in attachments
            ]

            # 5. Build summary narrative
            first_user_msg = next((m.content for m in messages if m.role == "user"), "General discussion")
            summary_narrative = f"Conversation touching on {', '.join(topics[:4]) if topics else 'general requests'}. User asked: {first_user_msg[:120]}"

            # 6. Save/update ConversationSummary record
            existing_summary = session.scalar(
                select(ConversationSummary)
                .where(ConversationSummary.conversation_id == conversation_id)
                .order_by(ConversationSummary.created_at.desc())
            )
            if existing_summary:
                existing_summary.summary = summary_narrative
                existing_summary.topics_json = json.dumps(topics[:10])
                existing_summary.entities_json = json.dumps(entity_dicts)
            else:
                new_summary = ConversationSummary(
                    conversation_id=conversation_id,
                    summary=summary_narrative,
                    topics_json=json.dumps(topics[:10]),
                    entities_json=json.dumps(entity_dicts),
                    version=1,
                    generated=True,
                )
                session.add(new_summary)

            # 7. Update UserContinuityState
            continuity_state = session.scalar(
                select(UserContinuityState).where(UserContinuityState.owner_id == owner_id)
            )
            if not continuity_state:
                continuity_state = UserContinuityState(owner_id=owner_id)
                session.add(continuity_state)
                session.flush()

            # Update recent conversation IDs
            recent_ids = []
            try:
                recent_ids = json.loads(continuity_state.recent_conversation_ids_json)
            except Exception:
                pass
            if conversation_id not in recent_ids:
                recent_ids.insert(0, conversation_id)
                continuity_state.recent_conversation_ids_json = json.dumps(recent_ids[:20])

            # Update recurring topics
            rec_topics = []
            try:
                rec_topics = json.loads(continuity_state.recurring_topics_json)
            except Exception:
                pass
            for t in topics:
                if t not in rec_topics:
                    rec_topics.append(t)
            continuity_state.recurring_topics_json = json.dumps(rec_topics[:30])

            # Update recent assets
            if asset_dicts:
                recent_assets = []
                try:
                    recent_assets = json.loads(continuity_state.recent_asset_ids_json)
                except Exception:
                    pass
                for a in asset_dicts:
                    aid = a["asset_id"]
                    if aid not in recent_assets:
                        recent_assets.insert(0, aid)
                continuity_state.recent_asset_ids_json = json.dumps(recent_assets[:20])

            continuity_state.memory_revision += 1
            continuity_state.last_interaction_at = datetime.now(UTC)
            session.commit()

            return ConversationSummaryData(
                conversation_id=conversation_id,
                topics=topics,
                entities=entity_dicts,
                assets=asset_dicts,
                important_user_statements=user_texts[:5],
                updated_at=datetime.now(UTC),
            )
