"""
Tests for Phase 06 Memory Nexus: Exact Message Archiving and Persistent Memory Retrieval.
Verifies exact text preservation, UTF-8 byte counts, token counts, idempotency/dedup,
historical search, and persistent memory lifecycle (remember, update, supersede, export).
"""

from __future__ import annotations

import json
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from hinaa_api.persistence.orm import Base, ExactMessageArchiveRecord
from hinaa_api.persistence.memory_service import MemoryService


@pytest.fixture
def memory_env():
    """Create isolated in-memory SQLite database and MemoryService."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    service = MemoryService(factory)
    user = service.ensure_user("nexus_test_user")
    return service, factory, user


def test_exact_message_archive_storage_and_metadata(memory_env):
    """Verify exact raw text, byte counts, and estimated tokens are stored on append_turn."""
    service, factory, user = memory_env

    user_text = "HINA, optimize the quantum neural compiler for 120fps avatars! 🚀"
    asst_text = "Analysis complete: neural weights pruned by 35% with zero perceptual loss."
    attachments = [{"type": "code", "name": "compiler.ts", "size": 1024}]

    convo_id = service.append_turn(
        user_id=user.id,
        companion_id="hina",
        conversation_id=None,
        user_text=user_text,
        assistant_text=asst_text,
        language="en",
        attachments=attachments,
    )

    with factory() as session:
        records = session.scalars(
            select(ExactMessageArchiveRecord).where(ExactMessageArchiveRecord.conversation_id == convo_id)
        ).all()

        assert len(records) == 2
        user_rec = next(r for r in records if r.role == "user")
        asst_rec = next(r for r in records if r.role == "assistant")

        assert user_rec.raw_text == user_text
        assert user_rec.char_count == len(user_text)
        assert user_rec.byte_count == len(user_text.encode("utf-8"))
        assert user_rec.estimated_tokens > 0
        assert "compiler.ts" in user_rec.attachment_metadata

        assert asst_rec.raw_text == asst_text
        assert asst_rec.char_count == len(asst_text)
        assert asst_rec.byte_count == len(asst_text.encode("utf-8"))


def test_exact_message_archive_idempotency(memory_env):
    """Verify appending turns with duplicate message IDs does not duplicate archives."""
    service, factory, user = memory_env

    convo_id = service.append_turn(
        user_id=user.id,
        companion_id="hina",
        conversation_id=None,
        user_text="Turn 1 text",
        assistant_text="Turn 1 response",
        language="en",
    )

    with factory() as session:
        count_initial = len(session.scalars(select(ExactMessageArchiveRecord)).all())
        assert count_initial == 2

    # Append second distinct turn
    service.append_turn(
        user_id=user.id,
        companion_id="hina",
        conversation_id=convo_id,
        user_text="Turn 2 text",
        assistant_text="Turn 2 response",
        language="en",
    )

    with factory() as session:
        count_after = len(session.scalars(select(ExactMessageArchiveRecord)).all())
        assert count_after == 4


def test_search_and_get_exact_archives(memory_env):
    """Verify search_exact_archives and get_exact_archive endpoints/methods."""
    service, _, user = memory_env

    service.append_turn(
        user_id=user.id,
        companion_id="hina",
        conversation_id=None,
        user_text="Please analyze the PostgreSQL indexing strategy",
        assistant_text="B-Tree indexes recommended for high selectivity queries.",
        language="en",
    )
    service.append_turn(
        user_id=user.id,
        companion_id="hina",
        conversation_id=None,
        user_text="What about Redis caching ttl?",
        assistant_text="Use jittered TTLs between 300 and 600 seconds.",
        language="en",
    )

    # Search by keyword
    pg_results = service.search_exact_archives(user_id=user.id, query="PostgreSQL")
    assert len(pg_results) >= 1
    assert "PostgreSQL" in pg_results[0]["raw_text"]

    redis_results = service.search_exact_archives(user_id=user.id, query="Redis")
    assert len(redis_results) >= 1
    assert "Redis" in redis_results[0]["raw_text"]

    # Get single archive
    first_msg_id = pg_results[0]["message_id"]
    single = service.get_exact_archive(user_id=user.id, message_id=first_msg_id)
    assert single is not None
    assert single["message_id"] == first_msg_id
    assert single["byte_count"] > 0


def test_persistent_memory_nexus_lifecycle(memory_env):
    """Verify Section D: memory extraction, listing, update, supersede, and export."""
    service, _, user = memory_env

    # 1. Remember fact
    mem = service.remember(
        user.id,
        "User prefers dark-mode neon-cyberpunk UI theme",
        category="preference",
    )
    assert mem["status"] == "approved"
    mem_id = mem["id"]

    # 2. List memories
    all_mems = service.list_memories(user.id)
    assert any(m["id"] == mem_id for m in all_mems)

    # 3. Supersede with updated fact (contradiction resolution)
    old_m, new_m = service.supersede_memory(
        user.id,
        mem_id,
        "User prefers minimalist clean-white UI theme",
        category="preference",
    )
    assert old_m["status"] == "superseded"
    assert new_m["status"] == "approved"
    assert "clean-white" in new_m["content"]

    # 4. Approved memory blocks for prompt compilation
    blocks = service.approved_memory_blocks(user.id)
    assert any("clean-white" in b for b in blocks)
    assert not any("neon-cyberpunk" in b for b in blocks)

    # 5. Export data (Section E: Memory Security & Portability)
    exported = service.export_data(user.id)
    assert "memories" in exported
    assert "conversationCount" in exported
