from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from ..errors import HinaaError
from .orm import (
    AuditEvent,
    Conversation,
    ConversationEntity,
    ConversationSummary,
    EpisodicMemory,
    ExplicitMemory,
    MemoryConsent,
    Message,
    MessageAttachment,
    TrainingExampleCandidate,
    User,
)

SENSITIVE = re.compile(
    r"\b(password|api[_ ]?key|ssn|credit card|bank account|biometric)\b",
    re.IGNORECASE,
)
ENTITY_NAME_RE = re.compile(
    r"\b(?:character(?:\s+girl)?|girl|hero|companion)?\s*(?:named|called)\s+([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
FIRST_PERSON_GOAL_RE = re.compile(
    r"\b(?:create|make|build|generate|design|continue|draw|produce|render|craft)\b.*",
    re.IGNORECASE,
)


def _json_loads(val: Any, default: Any = None) -> Any:
    if not val:
        return default
    try:
        return json.loads(val)
    except Exception:
        return default


def _empty_summary() -> dict[str, Any]:
    return {
        "current_goal": None,
        "unfinished_tasks": [],
        "open_questions": [],
        "important_entities": [],
        "important_assets": [],
        "companion_id": "hinaa",
        "updated_at": None,
    }


def _summary_payload(summary_raw: str | None) -> dict[str, Any]:
    if not summary_raw:
        return {}
    try:
        data = json.loads(summary_raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"summary": summary_raw}


def _bounded_append(items: list[Any], item: Any, limit: int = 10) -> list[Any]:
    out = [i for i in items if i != item]
    out.append(item)
    return out[-limit:]


def _normalize(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip().lower())


def _hash(content: str) -> str:
    return hashlib.sha256(_normalize(content).encode("utf-8")).hexdigest()


class MemoryService:
    """Consent-controlled durable memory. pgvector intentionally deferred."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def ensure_user(self, auth_subject: str) -> User:
        with self._factory() as session:
            user = session.scalar(select(User).where(User.auth_subject == auth_subject))
            if user is None:
                user = User(auth_subject=auth_subject)
                session.add(user)
                session.flush()
                session.add(
                    MemoryConsent(
                        user_id=user.id,
                        purpose="explicit_memory",
                        action="account_created",
                    )
                )
                session.commit()
                session.refresh(user)
            return user

    def set_memory_enabled(self, user_id: str, enabled: bool) -> dict[str, object]:
        with self._factory() as session:
            user = self._user(session, user_id)
            user.memory_enabled = enabled
            session.add(
                MemoryConsent(
                    user_id=user.id,
                    purpose="explicit_memory",
                    action="enable" if enabled else "disable",
                )
            )
            session.add(
                AuditEvent(
                    user_id=user.id,
                    action="memory.toggle",
                    resource_type="user",
                    resource_id=user.id,
                    result="ok",
                )
            )
            session.commit()
            return {"memoryEnabled": user.memory_enabled}

    def remember(
        self,
        user_id: str,
        content: str,
        *,
        category: str = "other",
        source_turn_ref: str | None = None,
        explicit: bool = True,
    ) -> dict[str, object]:
        text = content.strip()
        if not text or len(text) > 500:
            raise HinaaError("MEMORY_INVALID", "Memory content is empty or too long.", 422, False)
        if SENSITIVE.search(text):
            raise HinaaError(
                "MEMORY_SENSITIVE_BLOCKED",
                "That looks like sensitive credential data and was not stored.",
                422,
                False,
            )
        with self._factory() as session:
            user = self._user(session, user_id)
            if not user.memory_enabled:
                raise HinaaError(
                    "MEMORY_DISABLED",
                    "Memory is disabled. Enable it in privacy settings first.",
                    409,
                    True,
                )
            digest = _hash(text)
            existing = session.scalar(
                select(ExplicitMemory).where(
                    ExplicitMemory.user_id == user.id,
                    ExplicitMemory.normalized_hash == digest,
                    ExplicitMemory.deleted_at.is_(None),
                )
            )
            if existing is not None:
                existing.updated_at = datetime.now(UTC)
                session.commit()
                return self._public_memory(existing)
            status = "approved" if explicit else "pending"
            memory = ExplicitMemory(
                user_id=user.id,
                content=text,
                normalized_hash=digest,
                category=category,
                status=status,
                consent_state="explicit" if explicit else "pending",
                source_turn_ref=source_turn_ref,
            )
            session.add(memory)
            session.flush()
            session.add(
                MemoryConsent(
                    user_id=user.id,
                    purpose="explicit_memory",
                    action="remember",
                )
            )
            session.add(
                AuditEvent(
                    user_id=user.id,
                    action="memory.remember",
                    resource_type="memory",
                    resource_id=memory.id,
                    result="ok",
                )
            )
            session.commit()
            session.refresh(memory)
            return self._public_memory(memory)

    def list_memories(self, user_id: str) -> list[dict[str, object]]:
        with self._factory() as session:
            self._user(session, user_id)
            rows = session.scalars(
                select(ExplicitMemory)
                .where(
                    ExplicitMemory.user_id == user_id,
                    ExplicitMemory.deleted_at.is_(None),
                    ExplicitMemory.status.in_(("approved", "pending")),
                )
                .order_by(ExplicitMemory.created_at.desc())
            ).all()
            return [self._public_memory(row) for row in rows]

    def forget(self, user_id: str, memory_id: str) -> dict[str, object]:
        with self._factory() as session:
            memory = session.scalar(
                select(ExplicitMemory).where(
                    ExplicitMemory.id == memory_id,
                    ExplicitMemory.user_id == user_id,
                    ExplicitMemory.deleted_at.is_(None),
                )
            )
            if memory is None:
                raise HinaaError("MEMORY_NOT_FOUND", "That memory was not found.", 404, False)
            memory.deleted_at = datetime.now(UTC)
            memory.status = "revoked"
            session.add(
                AuditEvent(
                    user_id=user_id,
                    action="memory.forget",
                    resource_type="memory",
                    resource_id=memory_id,
                    result="ok",
                )
            )
            session.commit()
            return {"forgotten": True, "id": memory_id}

    def update_memory(
        self, user_id: str, memory_id: str, content: str, expires_at: datetime | None = None
    ) -> dict[str, object]:
        text = content.strip()
        if not text or len(text) > 500:
            raise HinaaError("MEMORY_INVALID", "Memory content is empty or too long.", 422, False)
        if SENSITIVE.search(text):
            raise HinaaError(
                "MEMORY_SENSITIVE_BLOCKED",
                "That looks like sensitive credential data and was not stored.",
                422,
                False,
            )
        with self._factory() as session:
            memory = session.scalar(
                select(ExplicitMemory).where(
                    ExplicitMemory.id == memory_id,
                    ExplicitMemory.user_id == user_id,
                    ExplicitMemory.deleted_at.is_(None),
                )
            )
            if memory is None:
                raise HinaaError("MEMORY_NOT_FOUND", "That memory was not found.", 404, False)
            memory.content = text
            memory.expires_at = expires_at
            memory.updated_at = datetime.now(UTC)
            session.add(
                AuditEvent(
                    user_id=user_id,
                    action="memory.update",
                    resource_type="memory",
                    resource_id=memory_id,
                    result="ok",
                )
            )
            session.commit()
            session.refresh(memory)
            return self._public_memory(memory)

    def supersede_memory(
        self,
        user_id: str,
        old_memory_id: str,
        new_content: str,
        *,
        category: str | None = None,
        source_turn_ref: str | None = None,
    ) -> tuple[dict[str, object], dict[str, object]]:
        text = new_content.strip()
        if not text or len(text) > 500:
            raise HinaaError("MEMORY_INVALID", "Memory content is empty or too long.", 422, False)
        if SENSITIVE.search(text):
            raise HinaaError(
                "MEMORY_SENSITIVE_BLOCKED",
                "That looks like sensitive credential data and was not stored.",
                422,
                False,
            )
        with self._factory() as session:
            user = self._user(session, user_id)
            if not user.memory_enabled:
                raise HinaaError(
                    "MEMORY_DISABLED",
                    "Memory is disabled. Enable it in privacy settings first.",
                    409,
                    True,
                )
            old_mem = session.scalar(
                select(ExplicitMemory).where(
                    ExplicitMemory.id == old_memory_id,
                    ExplicitMemory.user_id == user.id,
                    ExplicitMemory.deleted_at.is_(None),
                )
            )
            if old_mem is None:
                raise HinaaError("MEMORY_NOT_FOUND", "That memory was not found.", 404, False)

            old_mem.status = "superseded"
            old_mem.updated_at = datetime.now(UTC)

            new_digest = _hash(text)
            new_mem = ExplicitMemory(
                user_id=user.id,
                content=text,
                normalized_hash=new_digest,
                category=category or old_mem.category,
                status="approved",
                consent_state="explicit",
                source_turn_ref=source_turn_ref or f"supersedes:{old_mem.id}",
            )
            session.add(new_mem)
            session.flush()

            session.add(
                AuditEvent(
                    user_id=user.id,
                    action="memory.supersede",
                    resource_type="memory",
                    resource_id=new_mem.id,
                    result="ok",
                )
            )
            session.commit()
            session.refresh(old_mem)
            session.refresh(new_mem)
            return self._public_memory(old_mem), self._public_memory(new_mem)

    def approved_memory_blocks(self, user_id: str, limit: int = 8) -> tuple[str, ...]:
        with self._factory() as session:
            user = session.scalar(select(User).where(User.id == user_id))
            if user is None or not user.memory_enabled:
                return ()
            rows = session.scalars(
                select(ExplicitMemory)
                .where(
                    ExplicitMemory.user_id == user_id,
                    ExplicitMemory.deleted_at.is_(None),
                    ExplicitMemory.status == "approved",
                    or_(ExplicitMemory.expires_at.is_(None), ExplicitMemory.expires_at > datetime.now(UTC)),
                )
                .order_by(ExplicitMemory.updated_at.desc())
                .limit(limit)
            ).all()
            return tuple(f"memory:{row.id}: {row.content}" for row in rows)

    def append_turn(
        self,
        user_id: str,
        companion_id: str,
        conversation_id: str | None,
        user_text: str,
        assistant_text: str,
        language: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        with self._factory() as session:
            self._user(session, user_id)
            conversation: Conversation | None = None
            if conversation_id:
                conversation = session.scalar(
                    select(Conversation).where(
                        Conversation.id == conversation_id,
                        Conversation.user_id == user_id,
                    )
                )
            if conversation is None:
                conversation = Conversation(user_id=user_id, companion_id=companion_id)
                session.add(conversation)
                session.flush()

            user_msg = Message(
                conversation_id=conversation.id,
                role="user",
                content=user_text,
                language=language,
            )
            session.add(user_msg)
            session.flush()

            if attachments:
                for idx, att in enumerate(attachments):
                    asset_id = att.get("asset_id") or att.get("assetId") or att.get("id")
                    if not asset_id:
                        continue
                    session.add(
                        MessageAttachment(
                            message_id=user_msg.id,
                            asset_id=str(asset_id),
                            kind=str(att.get("kind", "image")),
                            mime_type=str(att.get("mime_type") or att.get("mimeType", "image/png")),
                            filename=str(att.get("filename", "attachment")),
                            size_bytes=int(att.get("size_bytes") or att.get("sizeBytes", 0)),
                            sha256=str(att.get("sha256", "")),
                            ordinal=int(att.get("ordinal", idx)),
                            role=att.get("role"),
                            url=att.get("url") or f"/v1/assets/{asset_id}/file",
                        )
                    )

            asst_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                language=language,
            )
            session.add(asst_msg)
            session.flush()

            entities = self._upsert_turn_entities(
                session,
                user_id=user_id,
                conversation_id=conversation.id,
                message_id=user_msg.id,
                user_text=user_text,
                assets=attachments or [],
            )
            self._record_episodic_events(
                session,
                user_id=user_id,
                conversation_id=conversation.id,
                message_id=user_msg.id,
                user_text=user_text,
                entities=entities,
                assets=attachments or [],
            )
            self._record_training_candidate(
                session,
                user_id=user_id,
                conversation_id=conversation.id,
                source_message_id=user_msg.id,
                assistant_message_id=asst_msg.id,
                user_text=user_text,
                assistant_text=assistant_text,
                language=language,
                companion_id=companion_id,
                entities=entities,
                assets=attachments or [],
            )

            count = len(
                session.scalars(
                    select(Message).where(
                        Message.conversation_id == conversation.id,
                        Message.deleted_at.is_(None),
                    )
                ).all()
            )
            summary_dict = self._build_structured_summary(
                session,
                conversation.id,
                companion_id=companion_id,
            )
            session.add(
                ConversationSummary(
                    conversation_id=conversation.id,
                    summary=json.dumps(summary_dict, ensure_ascii=False),
                    version=(count // 12) + 1,
                    generated=True,
                )
            )
            session.commit()
            return conversation.id

    def clear_conversation(self, user_id: str, conversation_id: str) -> dict[str, object]:
        with self._factory() as session:
            conversation = session.scalar(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                )
            )
            if conversation is None:
                raise HinaaError("CONVERSATION_NOT_FOUND", "Conversation not found.", 404, False)
            now = datetime.now(UTC)
            for message in conversation.messages:
                message.deleted_at = now
            conversation.ended_at = now
            session.add(
                AuditEvent(
                    user_id=user_id,
                    action="conversation.clear",
                    resource_type="conversation",
                    resource_id=conversation_id,
                    result="ok",
                )
            )
            session.commit()
            return {"cleared": True, "conversationId": conversation_id}

    def export_data(self, user_id: str) -> dict[str, object]:
        with self._factory() as session:
            user = self._user(session, user_id)
            memories = self.list_memories(user_id)
            conversations = session.scalars(
                select(Conversation).where(Conversation.user_id == user_id)
            ).all()
            return {
                "userId": user.id,
                "memoryEnabled": user.memory_enabled,
                "exportedAt": datetime.now(UTC).isoformat(),
                "memories": memories,
                "conversationCount": len(conversations),
                "note": "Export excludes deleted content and never includes provider secrets.",
            }

    def delete_all_memories(self, user_id: str) -> dict[str, object]:
        with self._factory() as session:
            self._user(session, user_id)
            now = datetime.now(UTC)
            for memory in session.scalars(
                select(ExplicitMemory).where(
                    ExplicitMemory.user_id == user_id,
                    ExplicitMemory.deleted_at.is_(None),
                )
            ):
                memory.deleted_at = now
                memory.status = "revoked"
            session.add(
                AuditEvent(
                    user_id=user_id,
                    action="memory.clear_all",
                    resource_type="user",
                    resource_id=user_id,
                    result="ok",
                )
            )
            session.commit()
            return {"cleared": True}

    def delete_all(self, user_id: str) -> dict[str, object]:
        with self._factory() as session:
            user = self._user(session, user_id)
            now = datetime.now(UTC)
            for memory in session.scalars(
                select(ExplicitMemory).where(ExplicitMemory.user_id == user_id)
            ):
                memory.deleted_at = now
                memory.status = "revoked"
            for conversation in session.scalars(
                select(Conversation).where(Conversation.user_id == user_id)
            ):
                conversation.ended_at = now
                for message in conversation.messages:
                    message.deleted_at = now
            user.deleted_at = now
            user.status = "deleted"
            user.memory_enabled = False
            session.add(
                AuditEvent(
                    user_id=user_id,
                    action="account.delete_all",
                    resource_type="user",
                    resource_id=user_id,
                    result="ok",
                )
            )
            session.commit()
            return {"deleted": True}

    def privacy_status(self, user_id: str) -> dict[str, object]:
        with self._factory() as session:
            user = self._user(session, user_id)
            active = len(
                session.scalars(
                    select(ExplicitMemory).where(
                        ExplicitMemory.user_id == user_id,
                        ExplicitMemory.deleted_at.is_(None),
                        ExplicitMemory.status == "approved",
                    )
                ).all()
            )
            return {
                "memoryEnabled": user.memory_enabled,
                "activeMemoryCount": active,
                "policyVersion": "privacy-1.0.0",
                "retention": {
                    "rawAudio": "not stored by default",
                    "deletedPurgeDays": 30,
                    "summariesAreGenerated": True,
                },
                "providers": {
                    "gemini": "conversation text when real mode enabled",
                    "azureSpeech": "audio stream when real mode enabled",
                },
            }

    def list_conversations(self, user_id: str, *, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return recent conversations for a user, newest first."""
        with self._factory() as session:
            from sqlalchemy import func, select
            from .orm import Conversation, Message
            
            # Subquery for last message and count
            msg_count = (
                select(func.count(Message.id))
                .where(Message.conversation_id == Conversation.id)
                .where(Message.deleted_at.is_(None))
                .correlate(Conversation)
                .scalar_subquery()
            )
            
            convos = (
                session.query(Conversation)
                .filter(Conversation.user_id == user_id)
                .filter(Conversation.ended_at.is_(None))
                .order_by(Conversation.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            
            results = []
            for c in convos:
                # Get last message preview
                last_msg = (
                    session.query(Message)
                    .filter(Message.conversation_id == c.id)
                    .filter(Message.deleted_at.is_(None))
                    .order_by(Message.created_at.desc())
                    .first()
                )
                preview = ""
                if last_msg:
                    if last_msg.role == "user":
                        preview = last_msg.content[:100] if last_msg.content else ""
                    else:
                        # Assistant content is JSON, extract displayText
                        try:
                            import json
                            data = json.loads(last_msg.content)
                            preview = (data.get("displayText") or "")[:100]
                        except Exception:
                            preview = (last_msg.content or "")[:100]
                
                msg_ct = (
                    session.query(func.count(Message.id))
                    .filter(Message.conversation_id == c.id)
                    .filter(Message.deleted_at.is_(None))
                    .scalar()
                )
                
                results.append({
                    "id": c.id,
                    "title": c.title or preview[:60] or "New conversation",
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "message_count": msg_ct or 0,
                    "last_message_preview": preview,
                    "companion_id": c.companion_id,
                })
            return results

    def get_conversation_messages(self, user_id: str, conversation_id: str, *, limit: int = 100, offset: int = 0) -> list[dict]:
        """Return messages for a conversation, oldest first."""
        with self._factory() as session:
            from .orm import Conversation, Message
            
            # Verify ownership
            convo = (
                session.query(Conversation)
                .filter(Conversation.id == conversation_id)
                .filter(Conversation.user_id == user_id)
                .first()
            )
            if not convo:
                return []
            
            messages = (
                session.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .filter(Message.deleted_at.is_(None))
                .order_by(Message.created_at.asc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            
            results = []
            for m in messages:
                content = m.content or ""
                display_text = content
                spoken_text = None
                if m.role == "assistant":
                    try:
                        import json
                        data = json.loads(content)
                        display_text = data.get("displayText", content)
                        spoken_text = data.get("spokenText")
                    except Exception:
                        pass
                msg_attachments = []
                if hasattr(m, "attachments") and m.attachments:
                    for att in m.attachments:
                        msg_attachments.append({
                            "asset_id": att.asset_id,
                            "filename": att.filename,
                            "mime_type": att.mime_type,
                            "size_bytes": att.size_bytes,
                            "kind": att.kind,
                            "role": att.role,
                            "url": att.url or f"/v1/assets/{att.asset_id}/file",
                        })

                results.append({
                    "id": m.id,
                    "role": m.role,
                    "content": display_text,
                    "spoken_text": spoken_text,
                    "language": m.language,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "attachments": msg_attachments,
                })
            return results

    def update_conversation_title(self, user_id: str, conversation_id: str, title: str) -> bool:
        """Update a conversation's title. Returns True if successful."""
        with self._factory() as session:
            from .orm import Conversation
            convo = (
                session.query(Conversation)
                .filter(Conversation.id == conversation_id)
                .filter(Conversation.user_id == user_id)
                .first()
            )
            if not convo:
                return False
            convo.title = title[:200]
            session.commit()
            return True

    @staticmethod
    def _entity_public(entity: ConversationEntity) -> dict[str, Any]:
        return {
            "id": entity.id,
            "entityType": entity.entity_type,
            "displayName": entity.display_name,
            "normalizedName": entity.normalized_name,
            "aliases": _json_loads(entity.aliases_json, []),
            "assetId": entity.asset_id,
            "sourceMessageId": entity.source_message_id,
            "createdAt": entity.created_at.isoformat() if entity.created_at else None,
            "updatedAt": entity.updated_at.isoformat() if entity.updated_at else None,
        }

    def _upsert_turn_entities(
        self,
        session: Session,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
        user_text: str,
        assets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        candidates: list[tuple[str, str, list[str], str | None]] = []
        for match in ENTITY_NAME_RE.finditer(user_text):
            name = match.group(1).strip(" ,.;:")
            if len(name) >= 2:
                entity_type = (
                    "character"
                    if "girl" in match.group(0).lower() or "character" in match.group(0).lower()
                    else "entity"
                )
                candidates.append((entity_type, name, [name.lower()], None))
        for asset in assets:
            kind = str(asset.get("kind") or "asset")
            asset_id = str(asset.get("asset_id") or asset.get("assetId") or "")
            if not asset_id:
                continue
            label = str(asset.get("filename") or asset_id)
            entity_type = "image" if kind == "image" else kind
            candidates.append((entity_type, label, [asset_id, label.lower()], asset_id))

        output: list[dict[str, Any]] = []
        for entity_type, display_name, aliases, asset_id in candidates:
            normalized = _normalize(display_name)[:240]
            entity = session.scalar(
                select(ConversationEntity).where(
                    ConversationEntity.user_id == user_id,
                    ConversationEntity.conversation_id == conversation_id,
                    ConversationEntity.entity_type == entity_type,
                    ConversationEntity.normalized_name == normalized,
                )
            )
            if entity is None:
                entity = ConversationEntity(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    entity_type=entity_type,
                    display_name=display_name[:240],
                    normalized_name=normalized,
                    aliases_json=json.dumps(sorted(set(aliases)), ensure_ascii=False),
                    source_message_id=message_id,
                    asset_id=asset_id,
                )
                session.add(entity)
                session.flush()
            else:
                existing_aliases = _json_loads(entity.aliases_json, [])
                if not isinstance(existing_aliases, list):
                    existing_aliases = []
                merged = sorted({str(a) for a in [*existing_aliases, *aliases] if a})
                entity.aliases_json = json.dumps(merged, ensure_ascii=False)
                entity.source_message_id = message_id
                entity.asset_id = entity.asset_id or asset_id
                entity.updated_at = datetime.now(UTC)
            output.append(self._entity_public(entity))
        return output

    def _record_episodic_events(
        self,
        session: Session,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
        user_text: str,
        entities: list[dict[str, Any]],
        assets: list[dict[str, Any]],
    ) -> None:
        lowered = user_text.lower()
        event: str | None = None
        event_type = "interaction"
        if any(word in lowered for word in ("approve", "approved", "keep this", "use this", "pasand")):
            event = f"User approved or preferred an output: {user_text[:240]}"
            event_type = "approval"
        elif any(word in lowered for word in ("reject", "rejected", "don't like", "not this", "redo")):
            event = f"User rejected or requested revision: {user_text[:240]}"
            event_type = "rejection"
        elif entities or assets:
            names = ", ".join(str(e.get("displayName")) for e in entities[:4] if e.get("displayName"))
            event = f"User referenced durable entities/assets: {names or user_text[:160]}"
            event_type = "entity_reference"
        if event:
            session.add(
                EpisodicMemory(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    event=event,
                    event_type=event_type,
                    source_message_id=message_id,
                    importance=2 if event_type in {"approval", "rejection"} else 1,
                )
            )

    def _record_training_candidate(
        self,
        session: Session,
        *,
        user_id: str,
        conversation_id: str,
        source_message_id: str,
        assistant_message_id: str,
        user_text: str,
        assistant_text: str,
        language: str,
        companion_id: str,
        entities: list[dict[str, Any]],
        assets: list[dict[str, Any]],
    ) -> None:
        metadata = {
            "language": language,
            "companion_id": companion_id,
            "assistant_message_id": assistant_message_id,
            "entity_ids": [entity.get("id") for entity in entities if entity.get("id")],
            "asset_ids": [
                asset.get("asset_id") or asset.get("assetId")
                for asset in assets
                if asset.get("asset_id") or asset.get("assetId")
            ],
            "training_policy": "offline_review_required",
            "online_weight_update": False,
        }
        session.add(
            TrainingExampleCandidate(
                user_id=user_id,
                conversation_id=conversation_id,
                source_message_id=source_message_id,
                candidate_type="conversation_turn",
                input_text=user_text[:8000],
                output_text=assistant_text[:12000],
                metadata_json=json.dumps(metadata, ensure_ascii=False),
                status="pending_review",
                quality_score=0,
            )
        )

    def _build_structured_summary(
        self,
        session: Session,
        conversation_id: str,
        *,
        companion_id: str,
    ) -> dict[str, Any]:
        previous = (
            session.query(ConversationSummary)
            .filter(ConversationSummary.conversation_id == conversation_id)
            .order_by(ConversationSummary.created_at.desc())
            .first()
        )
        summary = {**_empty_summary(), **_summary_payload(previous.summary if previous else None)}
        messages = (
            session.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .filter(Message.deleted_at.is_(None))
            .order_by(Message.created_at.desc())
            .limit(12)
            .all()
        )
        messages.reverse()
        entities = (
            session.query(ConversationEntity)
            .filter(ConversationEntity.conversation_id == conversation_id)
            .order_by(ConversationEntity.updated_at.desc())
            .limit(12)
            .all()
        )
        for message in messages:
            if message.role != "user":
                continue
            text = message.content or ""
            goal_match = FIRST_PERSON_GOAL_RE.search(text)
            if goal_match:
                summary["current_goal"] = goal_match.group(0).strip()
                summary["unfinished_tasks"] = _bounded_append(
                    list(summary.get("unfinished_tasks") or []),
                    {"message_id": message.id, "goal": goal_match.group(0).strip()},
                    limit=10,
                )
            if "?" in text:
                summary["open_questions"] = _bounded_append(
                    list(summary.get("open_questions") or []),
                    {"message_id": message.id, "question": text[:240]},
                    limit=10,
                )
        for entity in entities:
            summary["important_entities"] = _bounded_append(
                list(summary.get("important_entities") or []),
                self._entity_public(entity),
                limit=12,
            )
            if entity.asset_id:
                summary["important_assets"] = _bounded_append(
                    list(summary.get("important_assets") or []),
                    {"asset_id": entity.asset_id, "type": entity.entity_type, "name": entity.display_name},
                    limit=12,
                )
        summary["companion_id"] = companion_id
        summary["updated_at"] = datetime.now(UTC).isoformat()
        return summary

    def recent_working_context(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 12,
    ) -> dict[str, Any]:
        with self._factory() as session:
            conversation = session.scalar(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                )
            )
            if conversation is None:
                raise HinaaError("CONVERSATION_NOT_FOUND", "Conversation not found.", 404, False)

            all_messages = (
                session.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .filter(Message.deleted_at.is_(None))
                .order_by(Message.created_at.asc())
                .all()
            )
            messages = all_messages[-max(2, limit * 2):] if all_messages else []

            recent_messages = [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "language": m.language,
                    "createdAt": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ]

            summary_record = (
                session.query(ConversationSummary)
                .filter(ConversationSummary.conversation_id == conversation_id)
                .order_by(ConversationSummary.created_at.desc())
                .first()
            )
            rolling_summary = _summary_payload(summary_record.summary if summary_record else None)
            if not rolling_summary or not rolling_summary.get("current_goal"):
                rolling_summary = self._build_structured_summary(
                    session,
                    conversation_id,
                    companion_id=conversation.companion_id,
                )

            entities = (
                session.query(ConversationEntity)
                .filter(ConversationEntity.user_id == user_id)
                .filter(ConversationEntity.conversation_id == conversation_id)
                .order_by(ConversationEntity.updated_at.desc())
                .limit(20)
                .all()
            )

            episodic = (
                session.query(EpisodicMemory)
                .filter(EpisodicMemory.user_id == user_id)
                .filter(EpisodicMemory.conversation_id == conversation_id)
                .order_by(EpisodicMemory.created_at.desc())
                .limit(20)
                .all()
            )
            episodic.reverse()

            return {
                "conversationId": conversation_id,
                "recentMessages": recent_messages,
                "rollingSummary": rolling_summary,
                "entities": [self._entity_public(e) for e in entities],
                "episodicEvents": [
                    {
                        "id": ev.id,
                        "type": ev.event_type,
                        "event": ev.event,
                        "importance": ev.importance,
                        "createdAt": ev.created_at.isoformat() if ev.created_at else None,
                    }
                    for ev in episodic
                ],
                "updatedAt": datetime.now(UTC).isoformat(),
            }

    def resolve_reference_intent(
        self,
        user_id: str,
        conversation_id: str,
        text: str,
        project_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._factory() as session:
            conversation = session.scalar(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                )
            )
            if conversation is None:
                raise HinaaError("CONVERSATION_NOT_FOUND", "Conversation not found.", 404, False)

            lowered = text.lower()
            ref_keywords = (
                "continue", "keep", "her", "him", "them", "it", "this", "that",
                "previous", "before", "earlier", "like before", "like the previous",
                "same", "redo", "again", "modify", "change", "resume",
            )
            has_reference = any(k in lowered for k in ref_keywords)

            intent = "continue_task"
            if any(w in lowered for w in ("modify", "change", "redo", "like before", "make her", "adjust", "not this")):
                if "continue" in lowered and "like" in lowered:
                    intent = "continue_task"
                elif "redo" in lowered or "modify" in lowered or "change" in lowered:
                    intent = "modify_previous"
                else:
                    intent = "continue_task"
            elif "continue" in lowered or "proceed" in lowered or "resume" in lowered:
                intent = "continue_task"
            elif has_reference:
                intent = "continue_task"
            else:
                intent = "new_task"

            entities = (
                session.query(ConversationEntity)
                .filter(ConversationEntity.user_id == user_id)
                .filter(ConversationEntity.conversation_id == conversation_id)
                .order_by(ConversationEntity.updated_at.desc())
                .all()
            )
            target_entity = None
            if entities:
                for ent in entities:
                    if ent.display_name.lower() in lowered or ent.normalized_name in lowered:
                        target_entity = self._entity_public(ent)
                        break
                if not target_entity:
                    if any(p in lowered for p in ("her", "she", "girl")):
                        target_entity = next(
                            (self._entity_public(e) for e in entities if e.entity_type == "character"),
                            self._entity_public(entities[0]),
                        )
                    else:
                        target_entity = self._entity_public(entities[0])

            target_asset = None
            attachment = (
                session.query(MessageAttachment)
                .join(Message, MessageAttachment.message_id == Message.id)
                .filter(Message.conversation_id == conversation_id)
                .order_by(MessageAttachment.created_at.desc())
                .first()
            )
            if attachment:
                target_asset = {
                    "asset_id": attachment.asset_id,
                    "kind": attachment.kind,
                    "filename": attachment.filename,
                    "url": attachment.url,
                }
            elif target_entity and target_entity.get("assetId"):
                target_asset = {"asset_id": target_entity["assetId"]}

            summary_record = (
                session.query(ConversationSummary)
                .filter(ConversationSummary.conversation_id == conversation_id)
                .order_by(ConversationSummary.created_at.desc())
                .first()
            )
            summary_data = _summary_payload(summary_record.summary if summary_record else None)
            unfinished_task = None
            tasks = summary_data.get("unfinished_tasks") or []
            if tasks:
                unfinished_task = tasks[-1]
            elif summary_data.get("current_goal"):
                unfinished_task = {"goal": summary_data["current_goal"]}

            return {
                "hasReference": has_reference,
                "intent": intent,
                "targetEntity": target_entity,
                "targetAsset": target_asset,
                "unfinishedTask": unfinished_task,
                "resolutionSource": {
                    "recentMessages": True,
                    "rollingSummary": True,
                },
            }

    def list_training_candidates(
        self,
        user_id: str,
        status: str = "pending_review",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self._factory() as session:
            query = (
                session.query(TrainingExampleCandidate)
                .filter(TrainingExampleCandidate.user_id == user_id)
            )
            if status:
                query = query.filter(TrainingExampleCandidate.status == status)
            records = query.order_by(TrainingExampleCandidate.created_at.desc()).limit(limit).all()

            return [
                {
                    "id": r.id,
                    "conversationId": r.conversation_id,
                    "sourceMessageId": r.source_message_id,
                    "candidateType": r.candidate_type,
                    "inputText": r.input_text,
                    "outputText": r.output_text,
                    "status": r.status,
                    "qualityScore": r.quality_score,
                    "metadata": _json_loads(r.metadata_json, {}),
                    "createdAt": r.created_at.isoformat() if r.created_at else None,
                    "reviewedAt": r.reviewed_at.isoformat() if r.reviewed_at else None,
                }
                for r in records
            ]

    @staticmethod
    def _user(session: Session, user_id: str) -> User:
        user = session.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
        if user is None:
            raise HinaaError("USER_NOT_FOUND", "User was not found.", 404, False)
        return user

    @staticmethod
    def _public_memory(memory: ExplicitMemory) -> dict[str, object]:
        return {
            "id": memory.id,
            "content": memory.content,
            "category": memory.category,
            "status": memory.status,
            "consentState": memory.consent_state,
            "sourceTurnRef": memory.source_turn_ref,
            "expiresAt": memory.expires_at.isoformat() if memory.expires_at else None,
            "createdAt": memory.created_at.isoformat() if memory.created_at else None,
            "updatedAt": memory.updated_at.isoformat() if memory.updated_at else None,
        }

    @staticmethod
    def dump_export_json(payload: dict[str, object]) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2)
