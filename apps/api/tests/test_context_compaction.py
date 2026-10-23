"""
Tests for HINAA Context Micro-Compaction Subsystem.
Verifies that context pressure at the 75% threshold triggers non-destructive
micro-compaction, preserving active goals, recent turns, and avoiding context overflow.
"""

import pytest
from hinaa_api.config import get_settings
from hinaa_api.harness.compaction_worker import CompactionWorker
from hinaa_api.memory import SessionMemory
from hinaa_api.services import ConversationService


def test_compaction_worker_turns_compression():
    """Verifies that CompactionWorker summarizes older turns while keeping recent pairs intact."""
    worker = CompactionWorker(token_pressure_threshold=0.75)
    turns = [
        ("user", "Hello, I want to build a real-time trading dashboard."),
        ("assistant", "I can help with high-frequency telemetry and WebSockets."),
        ("user", "Let's use FastAPI and React with Vite."),
        ("assistant", "Sounds great, scaffolding the stack now."),
        ("user", "Now let's add automated unit tests."),
        ("assistant", "Writing pytest fixtures and mock test cases."),
        ("user", "Can you check the database migrations?"),
        ("assistant", "Checking alembic migrations now."),
    ]

    summary, compacted = worker.compact_conversation_turns(turns, keep_recent_pairs=2)
    assert "[Compacted Dialog Context:" in summary
    assert "trading dashboard" in summary or "FastAPI" in summary
    # compacted should contain summary user+assistant + 2 recent roundtrips (4 items) = 6 items
    assert len(compacted) == 6
    # Last 2 roundtrips must match original turns exactly
    assert compacted[-2:] == turns[-2:]


def test_session_memory_compact_if_needed():
    """Verifies that SessionMemory compacts entries when reaching 75% threshold."""
    # turn_limit=5 means _turn_limit=10 individual entries
    mem = SessionMemory(session_limit=10, turn_limit=5)
    session_id = "test_compact_session_1"

    # Add 4 turns (8 entries) -> 8/10 = 80% (>= 75% threshold)
    for i in range(4):
        mem.append_turn(session_id, f"User directive {i}: implement feature {i}", f"Assistant reply {i}")

    assert len(mem.context(session_id)) == 8

    # Trigger compaction
    summary = mem.compact_if_needed(session_id, threshold_ratio=0.75)
    assert summary is not None
    assert "[Compacted Context]:" in summary

    # Verify context after compaction: summary pair + last 2 turns (4 entries) = 6 entries
    compacted_ctx = mem.context(session_id)
    assert len(compacted_ctx) == 6
    assert "[Summary of earlier context:" in compacted_ctx[0][1]
    # Latest turn preserved verbatim
    assert compacted_ctx[-2] == ("user", "User directive 3: implement feature 3")
    assert compacted_ctx[-1] == ("assistant", "Assistant reply 3")


def test_conversation_service_compaction_integration():
    """Verifies that ConversationService._resolve_session_history invokes compaction at pressure."""
    settings = get_settings()
    # Force low limit for testing compaction behavior
    service = ConversationService(settings=settings)
    session_id = "test_conv_service_compact"

    # Populate session memory with 10 turns
    for i in range(8):
        service.memory.append_turn(session_id, f"Project request {i}", f"System execution {i}")

    # Set turn limit low so 16 entries exceed threshold
    service.memory._turn_limit = 16

    resolved = service._resolve_session_history(session_id=session_id, conversation_id=None)
    assert len(resolved) == 6
    assert "earlier context" in resolved[0][1]
    assert resolved[-1] == ("assistant", "System execution 7")
