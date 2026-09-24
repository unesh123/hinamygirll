"""test_cross_session_continuity_p0_5.py — P0.5 Cross-Session Continuity & Global Personal Memory OS

Validates that HINAA maintains persistent memory across chat boundaries:
"Same Hina. New Chat. Continuous Memory."

Scenarios tested:
1. Approved asset recall across chats (IMG_24 for Hina face).
2. Project architecture memory across chats (Nova uses PostgreSQL).
3. Unfinished task continuation across chats ("continue our Nova work" -> TASK_55).
4. Cross-session asset selection recall ("use the Gojo image I picked" -> IMG_82).
5. Global procedural preference across chats (short summary for reports).
6. Past conversation topic recall (Kung Fu Panda discussion).
7. Cross-session correction & supersession (black hair -> white hair).
8. Exact verbatim quotation recall ("What exactly did I say?").
9. Multi-project isolation (Nova vs Mika data isolation).
10. False memory protection (unmentioned topics return zero false evidence).
11. Conversation bootstrapper (compact user context & greeting recommendation).
12. Conversation finalizer (summary generation & continuity state refresh).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from hinaa_api.continuity import (
    ConversationBootstrapper,
    ConversationFinalizer,
    CrossSessionMemoryRetriever,
    MemoryPromotionService,
    MemoryScope,
    MemoryWriteAction,
    MemoryWritePolicy,
    UserContinuitySnapshot,
)
from hinaa_api.media.asset_store import get_asset_store
from hinaa_api.media.models import AssetKind, AssetRef, AssetSource
from hinaa_api.persistence.orm import (
    Base,
    Conversation,
    ConversationEntity,
    ConversationSummary,
    DurableTask,
    EpisodicMemory,
    ExplicitMemory,
    Message,
    MessageAttachment,
    User,
    UserContinuityState,
)


@pytest.fixture()
def db_session_factory():
    """Provides a fresh in-memory SQLite database session factory for each test."""
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # Seed default user
    with factory() as session:
        user = User(id="user-42", auth_subject="sub-42", status="active")
        session.add(user)
        session.commit()

    return factory


@pytest.fixture()
def retriever(db_session_factory) -> CrossSessionMemoryRetriever:
    return CrossSessionMemoryRetriever(db_session_factory)


@pytest.fixture()
def promotion_service(db_session_factory) -> MemoryPromotionService:
    return MemoryPromotionService(db_session_factory)


@pytest.fixture()
def bootstrapper(db_session_factory) -> ConversationBootstrapper:
    return ConversationBootstrapper(db_session_factory)


@pytest.fixture()
def finalizer(db_session_factory) -> ConversationFinalizer:
    return ConversationFinalizer(db_session_factory)


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Approved Asset Recall Across Chats
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_1_approved_asset_recall_across_chats(
    db_session_factory, retriever, promotion_service
):
    """Chat A: User sets 'My favorite reference for Hina is IMG_24. Always use this face.'
    Chat B: User says 'generate Hina.'
    Verify: IMG_24 is retrieved as approved reference without re-asking."""
    user_id = "user-42"
    convo_a = "convo-alpha-1"
    convo_b = "convo-beta-2"

    # In Chat A, promote IMG_24 as approved face for Hina
    promotion_service.promote_approved_asset(
        user_id,
        entity_name="Hina",
        asset_id="IMG_24",
        conversation_id=convo_a,
        description="Official approved character face",
    )

    # In Chat B (fresh conversation), user asks to generate Hina
    evidence = retriever.retrieve_relevant_context(
        user_id,
        "generate Hina sitting by the window",
        conversation_id=convo_b,
    )

    approved_matches = [e for e in evidence if e.source_type == "approved_asset"]
    assert len(approved_matches) >= 1
    assert approved_matches[0].source_id == "IMG_24"
    assert approved_matches[0].entity_id == "Hina"
    assert approved_matches[0].confidence == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Project Architecture Memory Across Chats
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_2_project_architecture_memory_across_chats(
    db_session_factory, retriever
):
    """Chat A: User establishes Nova stack: PostgreSQL, FastAPI, Next.js.
    Chat B: User asks 'What database are we using on Nova?'
    Verify: PostgreSQL is retrieved as project architecture fact."""
    user_id = "user-42"
    convo_a = "convo-alpha-1"
    convo_b = "convo-beta-2"

    # Seed project fact in Chat A
    with db_session_factory() as session:
        mem = ExplicitMemory(
            user_id=user_id,
            content="Nova uses PostgreSQL, FastAPI, and Next.js",
            normalized_hash="hash-nova-1",
            category="project",
            scope="project",
            project_id="Nova",
            status="approved",
            consent_state="explicit",
            source_turn_ref=f"convo:{convo_a}",
        )
        session.add(mem)
        session.commit()

    # Chat B query
    evidence = retriever.retrieve_relevant_context(
        user_id,
        "What database are we using on Nova?",
        conversation_id=convo_b,
    )

    project_matches = [e for e in evidence if e.source_type == "project"]
    assert len(project_matches) >= 1
    assert any("postgresql" in e.content.lower() for e in project_matches)
    assert project_matches[0].project_id == "Nova"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Unfinished Task Continuation Across Chats
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_3_unfinished_task_resumption_across_chats(
    db_session_factory, retriever
):
    """Chat A: User started task TASK_55 on Nova that is still in progress.
    Chat B: User says 'continue our Nova work.'
    Verify: TASK_55 is retrieved as unfinished task evidence."""
    user_id = "user-42"
    convo_a = "convo-alpha-1"
    convo_b = "convo-beta-2"

    with db_session_factory() as session:
        task = DurableTask(
            id="TASK_55",
            owner_id=user_id,
            project_id="Nova",
            conversation_id=convo_a,
            goal="Implement Nova authentication and billing modules",
            status="active",
        )
        session.add(task)
        session.commit()

    evidence = retriever.retrieve_relevant_context(
        user_id,
        "continue our Nova work",
        conversation_id=convo_b,
    )

    task_matches = [e for e in evidence if e.source_type == "unfinished_task"]
    assert len(task_matches) >= 1
    assert task_matches[0].source_id == "TASK_55"
    assert "billing modules" in task_matches[0].content


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Cross-Session Asset Selection Recall
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_4_cross_session_asset_selection_recall(
    db_session_factory, retriever
):
    """Chat A: User picked Gojo image IMG_82.
    Chat B: User says 'use the Gojo image I picked.'
    Verify: IMG_82 is retrieved."""
    user_id = "user-42"
    convo_b = "convo-beta-2"

    asset_store = get_asset_store()
    asset_store.register_asset_metadata(
        "IMG_82",
        owner_id=user_id,
        filename="gojo_satoru_blue_eyes.png",
        approval_state="selected",
        tags=["gojo", "selected", "jujutsu_kaisen"],
    )

    evidence = retriever.retrieve_relevant_context(
        user_id,
        "use the Gojo image I picked earlier",
        conversation_id=convo_b,
    )

    selected_matches = [e for e in evidence if e.source_type == "selected_asset"]
    assert len(selected_matches) >= 1
    assert selected_matches[0].source_id == "IMG_82"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Global Procedural Preference Across Chats
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_5_global_procedural_preference_across_chats(
    db_session_factory, retriever
):
    """Chat A: User says 'When you make coding reports, keep final summary short.'
    Chat B: User asks for a coding report.
    Verify: Preference is retrieved."""
    user_id = "user-42"
    convo_a = "convo-alpha-1"
    convo_b = "convo-beta-2"

    with db_session_factory() as session:
        pref = ExplicitMemory(
            user_id=user_id,
            content="When you make coding reports, keep final summary short",
            normalized_hash="hash-pref-1",
            category="preference",
            scope="user_global",
            status="approved",
            consent_state="explicit",
            source_turn_ref=f"convo:{convo_a}",
        )
        session.add(pref)
        session.commit()

    evidence = retriever.retrieve_relevant_context(
        user_id,
        "Prepare the weekly coding report for the team",
        conversation_id=convo_b,
    )

    pref_matches = [e for e in evidence if "keep final summary short" in e.content]
    assert len(pref_matches) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Past Conversation Topic Recall
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_6_historical_conversation_topic_retrieval(
    db_session_factory, retriever
):
    """Chat A: Discussed Kung Fu Panda's secret ingredient soup.
    Chat B: User asks 'what were we talking about when I mentioned Kung Fu Panda?'
    Verify: Conversation summary from Chat A is retrieved."""
    user_id = "user-42"
    convo_a = "convo-alpha-1"
    convo_b = "convo-beta-2"

    with db_session_factory() as session:
        c_a = Conversation(id=convo_a, user_id=user_id, companion_id="hinaa", title="Kung Fu Panda chat")
        c_b = Conversation(id=convo_b, user_id=user_id, companion_id="hinaa", title="New chat")
        session.add_all([c_a, c_b])
        session.flush()

        summary = ConversationSummary(
            conversation_id=convo_a,
            summary="User and Hina discussed Kung Fu Panda and Mr Ping's secret ingredient noodle soup.",
            topics_json=json.dumps(["Kung Fu Panda", "Noodles"]),
            version=1,
            generated=True,
        )
        session.add(summary)
        session.commit()

    evidence = retriever.retrieve_relevant_context(
        user_id,
        "what were we talking about when I mentioned Kung Fu Panda?",
        conversation_id=convo_b,
    )

    summary_matches = [e for e in evidence if e.source_type == "conversation_summary"]
    assert len(summary_matches) >= 1
    assert "kung fu panda" in summary_matches[0].content.lower()
    assert summary_matches[0].source_conversation_id == convo_a


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Cross-Session Correction & Supersession
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_7_correction_with_supersession(
    db_session_factory, retriever, promotion_service
):
    """Chat A: User says 'Hina hair color is black', then later 'Actually white hair from now on.'
    Chat B: User asks 'what hair color should she have?'
    Verify: Active memory is 'white hair', 'black hair' is marked as superseded."""
    user_id = "user-42"
    convo_a = "convo-alpha-1"
    convo_b = "convo-beta-2"

    # Old statement in Chat A
    with db_session_factory() as session:
        old_mem = ExplicitMemory(
            user_id=user_id,
            content="Hina hair color is black",
            normalized_hash="hash-hair-black",
            category="fact",
            scope="user_global",
            entity_id="Hina",
            status="approved",
            consent_state="explicit",
            source_turn_ref=f"convo:{convo_a}",
        )
        session.add(old_mem)
        session.commit()

    # User correction
    promotion_service.handle_user_correction(
        user_id,
        entity_name="Hina",
        attribute="hair color",
        new_value="white",
        conversation_id=convo_a,
    )

    # Verify in DB: old memory is superseded
    with db_session_factory() as session:
        mems = session.scalars(select(ExplicitMemory).where(ExplicitMemory.user_id == user_id)).all()
        black_mem = next(m for m in mems if "black" in m.content)
        white_mem = next(m for m in mems if "white" in m.content)

        assert black_mem.status == "superseded"
        assert black_mem.superseded_by_id == white_mem.id
        assert white_mem.status == "approved"

    # In Chat B, normal query retrieves ONLY the active (white hair) fact
    evidence = retriever.retrieve_relevant_context(
        user_id,
        "what hair color should Hina have in the new illustration?",
        conversation_id=convo_b,
    )
    hair_evidence = [e for e in evidence if "hair color is" in e.content]
    assert len(hair_evidence) >= 1
    assert "white" in hair_evidence[0].content
    assert "black" not in hair_evidence[0].content


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: Exact Verbatim Quotation Recall
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_8_exact_verbatim_quotation_recall(
    db_session_factory, retriever
):
    """Chat A: User says 'Deploy the nova worker to us-east-1 at 4pm sharp.'
    Chat B: User asks 'What exactly did I say?'
    Verify: Retrieves exact quote without paraphrase drift."""
    user_id = "user-42"
    convo_a = "convo-alpha-1"
    convo_b = "convo-beta-2"

    exact_quote = "Deploy the nova worker to us-east-1 at 4pm sharp."

    with db_session_factory() as session:
        c_a = Conversation(id=convo_a, user_id=user_id, companion_id="hinaa")
        c_b = Conversation(id=convo_b, user_id=user_id, companion_id="hinaa")
        session.add_all([c_a, c_b])
        session.flush()

        msg = Message(
            id="msg-101",
            conversation_id=convo_a,
            role="user",
            content=exact_quote,
        )
        session.add(msg)
        session.commit()

    evidence = retriever.retrieve_relevant_context(
        user_id,
        "What exactly did I say earlier?",
        conversation_id=convo_b,
    )

    quote_matches = [e for e in evidence if e.source_type == "message"]
    assert len(quote_matches) >= 1
    assert exact_quote in quote_matches[0].content
    assert quote_matches[0].metadata.get("exact_quote") == exact_quote


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: Multi-Project Isolation
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_9_multi_project_isolation(
    db_session_factory, retriever
):
    """Project Nova uses PostgreSQL; Project Mika uses MongoDB.
    When querying inside Project Nova context, Mika's MongoDB fact is NEVER leaked."""
    user_id = "user-42"
    convo_b = "convo-beta-2"

    with db_session_factory() as session:
        mem_nova = ExplicitMemory(
            user_id=user_id,
            content="Project Nova database is PostgreSQL",
            normalized_hash="hash-nova-db",
            category="project",
            scope="project",
            project_id="Nova",
            status="approved",
            consent_state="explicit",
        )
        mem_mika = ExplicitMemory(
            user_id=user_id,
            content="Project Mika database is MongoDB",
            normalized_hash="hash-mika-db",
            category="project",
            scope="project",
            project_id="Mika",
            status="approved",
            consent_state="explicit",
        )
        session.add_all([mem_nova, mem_mika])
        session.commit()

    # Query with Project Nova active context
    evidence_nova = retriever.retrieve_relevant_context(
        user_id,
        "What database are we using?",
        conversation_id=convo_b,
        project_id="Nova",
    )

    # Must include Nova PostgreSQL
    assert any("postgresql" in e.content.lower() for e in evidence_nova)
    # Must NOT include Mika MongoDB
    assert not any("mongodb" in e.content.lower() for e in evidence_nova)


# ─────────────────────────────────────────────────────────────────────────────
# Test 10: False Memory Protection
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_10_false_memory_protection(
    db_session_factory, retriever
):
    """User asks about a concept never discussed ('Quantum warp coils').
    Verify: Retriever returns empty evidence, no hallucinated records."""
    user_id = "user-42"
    convo_b = "convo-beta-2"

    evidence = retriever.retrieve_relevant_context(
        user_id,
        "What did we decide about the quantum warp coils?",
        conversation_id=convo_b,
    )

    assert len(evidence) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Test 11: Conversation Bootstrapper
# ─────────────────────────────────────────────────────────────────────────────
def test_conversation_bootstrapper(
    db_session_factory, bootstrapper
):
    """Tests new chat bootstrapping with compact user continuity."""
    user_id = "user-42"

    with db_session_factory() as session:
        state = UserContinuityState(
            owner_id=user_id,
            preferred_name="Unesh",
            communication_style="concise",
            important_projects_json=json.dumps(["Nova", "Sakura"]),
            active_long_running_tasks_json=json.dumps([
                {"id": "TASK_1", "goal": "Deploy Sakura UI", "status": "running"}
            ]),
            important_entities_json=json.dumps([
                {"name": "Hina", "approved_face": "IMG_24"}
            ]),
            persistent_preferences_json=json.dumps([
                "Always run automated tests before commit"
            ]),
        )
        session.add(state)
        session.commit()

    boot = bootstrapper.bootstrap_new_conversation(user_id)
    snapshot = boot["snapshot"]
    assert snapshot.preferred_name == "Unesh"
    assert "Unesh" in boot["bootstrap_block"]
    assert "IMG_24" in boot["bootstrap_block"]
    assert "Deploy Sakura UI" in boot["bootstrap_block"]
    assert "Deploy Sakura UI" in boot["greeting_hint"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 12: Conversation Finalizer Idempotent Refresh
# ─────────────────────────────────────────────────────────────────────────────
def test_conversation_finalizer_idempotent_refresh(
    db_session_factory, finalizer
):
    """Tests finalizing a conversation flushes summary and updates UserContinuityState."""
    user_id = "user-42"
    convo_id = "convo-fin-1"

    with db_session_factory() as session:
        convo = Conversation(id=convo_id, user_id=user_id, companion_id="hinaa", title="Test finalizer")
        session.add(convo)
        session.flush()

        m1 = Message(id="m1", conversation_id=convo_id, role="user", content="Let's work on Project Nova")
        m2 = Message(id="m2", conversation_id=convo_id, role="assistant", content="Ready for Project Nova!")
        session.add_all([m1, m2])
        session.commit()

    # First finalization
    data1 = finalizer.finalize_conversation(user_id, convo_id)
    assert convo_id in data1.conversation_id
    assert "Nova" in data1.topics

    # Check UserContinuityState was created/updated
    with db_session_factory() as session:
        state = session.scalar(select(UserContinuityState).where(UserContinuityState.owner_id == user_id))
        assert state is not None
        assert state.memory_revision == 2  # 1 initial + 1 finalized
        rec_convos = json.loads(state.recent_conversation_ids_json)
        assert convo_id in rec_convos

    # Second finalization is idempotent
    data2 = finalizer.finalize_conversation(user_id, convo_id)
    assert "Nova" in data2.topics
