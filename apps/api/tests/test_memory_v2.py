from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hinaa_api.memory_v2 import (
    MemoryManagerV2,
    MemoryPartition,
    ProceduralMemoryRule,
    ProjectMemoryFact,
    SemanticMemoryItem,
    WorkingMemoryTurn,
)
from hinaa_api.persistence.memory_service import MemoryService
from hinaa_api.persistence.orm import Base


def test_memory_partitions_and_working_memory():
    manager = MemoryManagerV2(max_working_turns_per_convo=4)
    convo_id = "c_123"

    t1 = manager.add_turn(convo_id, "user", "Hello Hina")
    t2 = manager.add_turn(convo_id, "assistant", "Hello! How can I assist you today?")
    t3 = manager.add_turn(convo_id, "user", "Let's work on Project Titan.")
    t4 = manager.add_turn(convo_id, "assistant", "Understood. Titan architecture loaded.")
    t5 = manager.add_turn(convo_id, "user", "What's our next task?")

    turns = manager.get_working_turns(convo_id)
    # Bounds check: max 4 turns
    assert len(turns) == 4
    assert turns[0].turn_id == t2.turn_id
    assert turns[-1].content == "What's our next task?"

    manager.clear_working_memory(convo_id)
    assert len(manager.get_working_turns(convo_id)) == 0


def test_episodic_memory_and_filtering():
    manager = MemoryManagerV2()
    e1 = manager.record_event("User initiated data migration", event_type="action", importance=2, conversation_id="c_1")
    e2 = manager.record_event("Database connection timeout", event_type="error", importance=4, conversation_id="c_1")
    e3 = manager.record_event("Resolved connection timeout with retry policy", event_type="fix", importance=5, conversation_id="c_1")
    e4 = manager.record_event("Minor UI greeting rendered", event_type="ui", importance=1, conversation_id="c_2")

    c1_events = manager.get_events(conversation_id="c_1")
    assert len(c1_events) == 3

    high_imp = manager.get_events(min_importance=4)
    assert len(high_imp) == 2
    assert {e.event_id for e in high_imp} == {e2.event_id, e3.event_id}


def test_semantic_memory_supersession_and_temporal_validity():
    manager = MemoryManagerV2()
    user_id = "u_456"

    # 1. Store initial fact
    mem1 = manager.remember(user_id, "User lives in Seattle", category="fact")
    assert mem1.status == "active"
    assert mem1.superseded_by_id is None

    # 2. Store fact with past expiration
    past_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    mem_expired = manager.remember(user_id, "Temporary temporary discount code", category="fact", valid_until=past_time)
    assert mem_expired.is_temporally_valid is False

    # Active memories should only return mem1
    active_mems = manager.get_active_semantic_memories(user_id)
    assert len(active_mems) == 1
    assert active_mems[0].content == "User lives in Seattle"

    # 3. Supersede fact (user moved)
    old_item, new_item = manager.supersede_memory(user_id, mem1.memory_id, "User relocated and lives in Tokyo")
    assert old_item.status == "superseded"
    assert old_item.superseded_by_id == new_item.memory_id
    assert new_item.status == "active"
    assert new_item.content == "User relocated and lives in Tokyo"

    # Now active memories should only show Tokyo
    active_now = manager.get_active_semantic_memories(user_id)
    assert len(active_now) == 1
    assert active_now[0].content == "User relocated and lives in Tokyo"

    # Check that episodic audit event was created
    events = manager.get_events()
    assert any("Superseded memory" in e.description for e in events)


def test_procedural_and_project_memory():
    manager = MemoryManagerV2()

    # Procedural rules
    manager.add_rule(
        trigger_pattern=r"\b(build|deploy|release)\b",
        action_workflow="Run test suite -> verify lints -> build artifact -> deploy to staging",
        priority=10,
    )
    manager.add_rule(
        trigger_pattern=r"\b(format|lint)\b",
        action_workflow="Run ruff check and prettier",
        priority=5,
    )

    matches = manager.match_rules("Please deploy the new version")
    assert len(matches) == 1
    assert "Run test suite" in matches[0].action_workflow

    # Project facts
    manager.set_project_fact("proj_titan", "primary_db", "PostgreSQL", category="dependency")
    manager.set_project_fact("proj_titan", "target_qps", 15000, category="architecture")

    assert manager.get_project_fact("proj_titan", "primary_db") == "PostgreSQL"
    assert manager.get_project_fact("proj_titan", "target_qps") == 15000

    # Cross-partition compilation
    summary = manager.compile_partition_summary("u_1", project_id="proj_titan", query="Deploy now")
    assert summary["project_facts"]["primary_db"] == "PostgreSQL"
    assert len(summary["procedural_workflows"]) == 1


def test_database_backed_memory_service_supersede():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    service = MemoryService(factory)

    user = service.ensure_user("test_auth_sub")
    mem1 = service.remember(user.id, "Preferred language is Python", category="preference")
    assert mem1["status"] == "approved"

    old_mem, new_mem = service.supersede_memory(
        user.id,
        mem1["id"],
        "Preferred language updated to TypeScript",
        category="preference",
    )

    assert old_mem["status"] == "superseded"
    assert new_mem["status"] == "approved"
    assert new_mem["content"] == "Preferred language updated to TypeScript"
    assert "supersedes:" in new_mem["sourceTurnRef"]
