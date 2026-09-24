"""test_active_goal_constraints.py — Unit and Integration Verification for ActiveGoal & Hard Constraints

Tests:
1. ActiveGoal dataclass serialization (to_dict / from_dict).
2. DialogueStateService.extract_goal_and_constraints extracts goal & mandatory constraints.
3. build_dialogue_state_block formats ActiveGoal and constraints at Tier-0.
4. ORM roundtrip: saving and reloading ConversationTurnState with ActiveGoal preserves all fields.
5. Live API Stream: turns with goal & constraint instructions persist into dialogue state.
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.dialogue_state import (
    ActiveGoal,
    ConversationTurnState,
    DialogueStateService,
    build_dialogue_state_block,
)
from hinaa_api.main import create_app
from hinaa_api.persistence.db import get_session_factory
from hinaa_api.persistence.orm import ConversationTurnState as OrmState


def test_active_goal_serialization():
    goal = ActiveGoal(
        goal="Redesign Hina wardrobe",
        acceptance_criteria=["render in 4k", "include sakura petals"],
        hard_constraints=["never change the approved face", "always keep purple eyes"],
        known_facts=["Hina wears modern kimono"],
    )
    d = goal.to_dict()
    assert d["goal"] == "Redesign Hina wardrobe"
    assert len(d["hard_constraints"]) == 2
    assert "never change the approved face" in d["hard_constraints"]

    restored = ActiveGoal.from_dict(d)
    assert restored.goal == goal.goal
    assert restored.hard_constraints == goal.hard_constraints
    assert restored.acceptance_criteria == goal.acceptance_criteria
    assert restored.known_facts == goal.known_facts


def test_extract_goal_and_constraints():
    state = ConversationTurnState.empty("conv-101")
    text = "Our goal is to build a modern portfolio but never change the approved face and always keep purple eyes."
    DialogueStateService.extract_goal_and_constraints(state, text)

    assert state.active_goal is not None
    assert "build a modern portfolio" in state.active_goal.goal.lower()
    assert any("never change the approved face" in c.lower() for c in state.active_goal.hard_constraints)
    assert any("always keep purple eyes" in c.lower() for c in state.active_goal.hard_constraints)


def test_build_dialogue_state_block_renders_tier_0():
    state = ConversationTurnState.empty("conv-102")
    state.active_goal = ActiveGoal(
        goal="Improve avatar rendering",
        hard_constraints=["never touch the facial features"],
        acceptance_criteria=["achieve 60fps"],
    )
    block = build_dialogue_state_block(state)
    assert "🎯 ACTIVE GOAL: Improve avatar rendering" in block
    assert "⛔ HARD CONSTRAINTS (MANDATORY — NEVER VIOLATE):" in block
    assert "never touch the facial features" in block
    assert "📋 ACCEPTANCE CRITERIA:" in block
    assert "achieve 60fps" in block


def test_active_goal_sqlite_orm_roundtrip(tmp_path):
    db_path = tmp_path / "goal_test.db"
    settings = Settings(
        HINAA_DATABASE_URL=f"sqlite:///{db_path}",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
    )
    app = create_app(settings)
    session_factory = get_session_factory(settings)
    service = DialogueStateService(session_factory)

    state = ConversationTurnState.empty("conv-orm-1")
    state.active_goal = ActiveGoal(
        goal="Continuous intelligence deployment",
        hard_constraints=["never drop database records"],
    )
    service.save(state)

    # Reload fresh from DB
    loaded = service.load("conv-orm-1")
    assert loaded.active_goal is not None
    assert loaded.active_goal.goal == "Continuous intelligence deployment"
    assert loaded.active_goal.hard_constraints == ["never drop database records"]


def test_live_api_turn_persists_active_goal(tmp_path):
    db_path = tmp_path / "live_goal.db"
    settings = Settings(
        HINAA_DATABASE_URL=f"sqlite:///{db_path}",
        HINAA_AUTH_MODE="dev",
        HINAA_DEV_AUTH_SUBJECT="test-goal-user",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_PROVIDER_MODE="mock",
    )
    app = create_app(settings)
    client = TestClient(app)

    convo_id = "conv-live-goal-1"
    headers = {"X-HINAA-Dev-User": "test-goal-user", "X-Conversation-ID": convo_id}
    payload = {
        "sessionId": convo_id,
        "conversationId": convo_id,
        "text": "Our goal is to create high quality artwork but never change the face.",
        "providerMode": "mock",
        "companionId": "hinaa",
    }
    resp = client.post("/v1/conversations/turns:stream", json=payload, headers=headers)
    assert resp.status_code == 200

    # Verify dialogue state persisted with active_goal in SQLite
    session_factory = get_session_factory(settings)
    d_service = DialogueStateService(session_factory)
    persisted = d_service.load(convo_id, "test-goal-user")
    assert persisted.active_goal is not None
    assert any("never change the face" in hc.lower() for hc in persisted.active_goal.hard_constraints)
