from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..errors import HinaaError
from .orm import (
    AuditEvent,
    Conversation,
    ConversationSummary,
    ExplicitMemory,
    MemoryConsent,
    Message,
    User,
)

SENSITIVE = re.compile(
    r"\b(password|api[_ ]?key|ssn|credit card|bank account|biometric)\b",
    re.IGNORECASE,
)


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
                    resource_id=None,
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
            session.add(
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=user_text,
                    language=language,
                )
            )
            session.add(
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=assistant_text,
                    language=language,
                )
            )
            count = len(
                session.scalars(
                    select(Message).where(
                        Message.conversation_id == conversation.id,
                        Message.deleted_at.is_(None),
                    )
                ).all()
            )
            if count >= 12 and count % 12 == 0:
                session.add(
                    ConversationSummary(
                        conversation_id=conversation.id,
                        summary=(
                            "Generated summary (not a literal transcript): recent turns discussed "
                            f"companion={companion_id}. Details remain in message history until deleted."
                        ),
                        version=count // 12,
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
            "createdAt": memory.created_at.isoformat() if memory.created_at else None,
            "updatedAt": memory.updated_at.isoformat() if memory.updated_at else None,
        }

    @staticmethod
    def dump_export_json(payload: dict[str, object]) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2)
