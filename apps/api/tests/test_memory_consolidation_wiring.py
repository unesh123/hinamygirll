"""P1#2: consolidation wired to real turns, contradiction supersession,
hybrid retrieval scoring (relevance + recency + importance + confidence)."""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from hinaa_api.cognitive.consolidation import DurableMemoryAdapter, MemoryConsolidator  # noqa: E402
from hinaa_api.continuity.retriever import CrossSessionMemoryRetriever  # noqa: E402
from hinaa_api.persistence.memory_service import MemoryService  # noqa: E402
from hinaa_api.persistence.orm import Base, ExplicitMemory  # noqa: E402


def make_service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return MemoryService(factory), factory


def test_consolidation_learns_preference_from_turn():
    service, _ = make_service()
    user = service.ensure_user("auth_sub_a")
    result = MemoryConsolidator.consolidate_turn(
        user_id=user.id,
        user_text="I prefer dark mode everywhere",
        assistant_text="",
        memory_manager=DurableMemoryAdapter(service),
        conversation_id="session:test1",
    )
    assert result and result[0]["action"] == "added"
    memories = service.list_memories(user.id)
    assert any("dark mode" in m["content"].lower() for m in memories)
    # Auto-extracted facts are pending consent, not owner-approved
    assert all(m["status"] == "pending" for m in memories)


def test_contradiction_supersedes_old_fact_latest_wins():
    service, _ = make_service()
    user = service.ensure_user("auth_sub_b")
    adapter = DurableMemoryAdapter(service)

    MemoryConsolidator.consolidate_turn(
        user_id=user.id,
        user_text="I prefer dark mode",
        assistant_text="",
        memory_manager=adapter,
        conversation_id="session:t1",
    )
    result = MemoryConsolidator.consolidate_turn(
        user_id=user.id,
        user_text="Actually I prefer light mode now",
        assistant_text="",
        memory_manager=adapter,
        conversation_id="session:t2",
    )
    assert any(r["action"] == "superseded" for r in result)

    statuses = [(m["content"].lower(), m["status"]) for m in service.list_memories(user.id)]
    dark = [s for c, s in statuses if "dark mode" in c]
    light = [s for c, s in statuses if "light mode" in c]
    assert dark == [] or dark == ["superseded"] or "superseded" in dark
    assert light  # the new fact exists


def test_adapter_surface_matches_consolidator_expectations():
    service, _ = make_service()
    user = service.ensure_user("auth_sub_c")
    service.remember(user.id, "Preferred language is Nepali", category="preference")
    adapter = DurableMemoryAdapter(service)
    active = adapter.get_active_semantic_memories(user.id)
    assert len(active) == 1
    assert active[0].content == "Preferred language is Nepali"
    assert active[0].memory_id


def test_hybrid_retrieval_recency_outranks_stale_overlap():
    service, factory = make_service()
    user = service.ensure_user("auth_sub_d")
    stale = service.remember(user.id, "Project Titan uses React", category="preference")
    fresh = service.remember(user.id, "Project Titan uses Vite", category="preference")

    # Age the stale row by 60 days; keep the fresh one at now.
    with factory() as session:
        row = session.scalar(select(ExplicitMemory).where(ExplicitMemory.id == stale["id"]))
        row.updated_at = datetime.now(UTC) - timedelta(days=60)
        session.commit()

    retriever = CrossSessionMemoryRetriever(factory)
    evidence = retriever.retrieve_relevant_context(user.id, "titan")
    by_id = {e.source_id: e for e in evidence if e.source_type == "semantic_memory"}
    assert stale["id"] in by_id and fresh["id"] in by_id
    assert by_id[fresh["id"]].score > by_id[stale["id"]].score


def test_pending_observations_stay_invisible_to_retrieval():
    """Consent discipline: pending (auto-extracted) memories are stored for
    owner review but must NOT shape her answers until approved."""
    service, factory = make_service()
    user = service.ensure_user("auth_sub_e")
    approved = service.remember(user.id, "Loves anime marathons", category="preference", explicit=True)
    pending = service.remember(user.id, "Loves anime soundtracks", category="preference", explicit=False)
    assert pending["status"] == "pending"

    retriever = CrossSessionMemoryRetriever(factory)
    evidence = retriever.retrieve_relevant_context(user.id, "anime")
    ids = {e.source_id for e in evidence if e.source_type == "semantic_memory"}
    assert approved["id"] in ids
    assert pending["id"] not in ids


def test_consolidation_failure_never_raises():
    class BrokenService:
        def list_memories(self, user_id):
            raise RuntimeError("db down")

        def remember(self, *a, **k):
            raise RuntimeError("db down")

    # Consolidator calls go through hasattr guards; a broken store must not crash the turn.
    result = MemoryConsolidator.consolidate_turn(
        user_id="u_x",
        user_text="I prefer tea over coffee",
        assistant_text="",
        memory_manager=DurableMemoryAdapter(BrokenService()),
        conversation_id="session:x",
    )
    # remember raising propagates out of consolidate_turn? No: callers wrap in
    # try/except in services.py. Here the adapter surfaces the failure — the
    # contract we verify is that the adapter's read path degrades gracefully.
    assert isinstance(result, list)
