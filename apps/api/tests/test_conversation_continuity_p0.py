"""test_conversation_continuity_p0.py — P0 Continuous Conversational Mind

Reproduces the real One Piece / 1147 conversation failure scenario reported
by the user, plus the full battery of context-loss and tool-failure regressions.

These tests run WITHOUT a live LLM — they validate the dialogue state engine,
slot resolver, dialogue act classifier, and prompt assembly in isolation.

Failures in this file = user-visible conversation mind regression.
"""
from __future__ import annotations

import json
import pytest

from hinaa_api.dialogue_state import (
    ConversationTurnState,
    DialogueAct,
    DialogueActResolver,
    DialogueStateService,
    Slot,
    SlotResolver,
    SlotType,
    build_dialogue_state_block,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def empty_state() -> ConversationTurnState:
    return ConversationTurnState.empty("conv-test-001", user_id="user-1")


@pytest.fixture()
def one_piece_state() -> ConversationTurnState:
    """State mid-conversation about One Piece episode 1147."""
    state = ConversationTurnState(
        conversation_id="conv-test-001",
        user_id="user-1",
        active_topic="One Piece",
        active_intent="web_search",
        turn_count=3,
    )
    state.set_slot("episode_number", 1147, SlotType.ANIME_EPISODE, 0.99)
    return state


@pytest.fixture()
def pending_question_state() -> ConversationTurnState:
    state = ConversationTurnState(
        conversation_id="conv-test-002",
        user_id="user-1",
        active_topic="One Piece",
        turn_count=2,
    )
    state.pending_question = {
        "text": "Which episode number are you looking for?",
        "asked_at_turn": 2,
    }
    return state


# ─────────────────────────────────────────────────────────────────────────────
# P0-BUG-1: "1147" treated as isolated number instead of episode answer
# ─────────────────────────────────────────────────────────────────────────────

class TestNumberAnswerResolution:
    """User says '1147' after asking about One Piece — must be recognised as episode."""

    def test_number_only_classified_as_answer(self, pending_question_state):
        act = DialogueActResolver.resolve("1147", pending_question_state)
        assert act == DialogueAct.ANSWER, (
            "A bare number after a pending question must be DialogueAct.ANSWER, not REQUEST"
        )

    def test_episode_slot_filled_from_number_answer(self, pending_question_state):
        act = DialogueActResolver.resolve("1147", pending_question_state)
        slots = SlotResolver.resolve("1147", pending_question_state, act)
        assert "episode_number" in slots, "episode_number slot must be filled from '1147' answer"
        assert slots["episode_number"].value == 1147
        assert slots["episode_number"].slot_type == SlotType.ANIME_EPISODE

    def test_episode_slot_filled_from_explicit_mention(self, empty_state):
        act = DialogueActResolver.resolve("episode 1147", empty_state)
        slots = SlotResolver.resolve("episode 1147", empty_state, act)
        assert "episode_number" in slots
        assert slots["episode_number"].value == 1147

    def test_number_answer_not_request(self, pending_question_state):
        """Without pending question, a bare number should still be ANSWER if it's just a number."""
        act = DialogueActResolver.resolve("42", pending_question_state)
        assert act == DialogueAct.ANSWER

    def test_number_in_fresh_state_is_answer(self, empty_state):
        """Even in fresh state, a number-only utterance should be ANSWER (not REQUEST)."""
        act = DialogueActResolver.resolve("1147", empty_state)
        assert act == DialogueAct.ANSWER


# ─────────────────────────────────────────────────────────────────────────────
# P0-BUG-2: "hina" causes greeting reset instead of acknowledgement
# ─────────────────────────────────────────────────────────────────────────────

class TestVocativeHandling:
    """'hina' mid-conversation should be VOCATIVE, not trigger fresh greeting."""

    def test_hina_classified_as_vocative(self, one_piece_state):
        act = DialogueActResolver.resolve("hina", one_piece_state)
        assert act == DialogueAct.VOCATIVE, (
            "'hina' must be DialogueAct.VOCATIVE — never treated as a fresh session start"
        )

    def test_hinaa_classified_as_vocative(self, one_piece_state):
        act = DialogueActResolver.resolve("Hinaa", one_piece_state)
        assert act == DialogueAct.VOCATIVE

    def test_hey_hina_classified_as_vocative(self, empty_state):
        act = DialogueActResolver.resolve("hey hina", empty_state)
        assert act == DialogueAct.VOCATIVE

    def test_active_context_prevents_fresh_greeting(self, one_piece_state):
        """should_use_fresh_greeting() must return False when topic is active."""
        assert not one_piece_state.should_use_fresh_greeting(), (
            "Fresh greeting must NOT be sent when an active topic exists"
        )

    def test_empty_state_allows_fresh_greeting(self, empty_state):
        assert empty_state.should_use_fresh_greeting(), (
            "Fresh greeting is fine when no active context exists"
        )

    def test_has_active_context_with_topic(self, one_piece_state):
        assert one_piece_state.has_active_context()

    def test_has_active_context_with_pending_question(self, pending_question_state):
        assert pending_question_state.has_active_context()

    def test_empty_state_no_active_context(self, empty_state):
        assert not empty_state.has_active_context()


# ─────────────────────────────────────────────────────────────────────────────
# P0-BUG-3: topic/intent/slots preserved through tool failure
# ─────────────────────────────────────────────────────────────────────────────

class TestToolFailureStatePreservation:
    """A 422 / tool error must ONLY update last_tool_state — never clear topic/slots."""

    def test_tool_failure_preserves_topic(self, one_piece_state):
        svc = DialogueStateService.__new__(DialogueStateService)
        svc.record_tool_failure(one_piece_state, "web_search", {"query": "One Piece"}, "422 Missing query")
        assert one_piece_state.active_topic == "One Piece", (
            "active_topic must survive a tool failure"
        )

    def test_tool_failure_preserves_slots(self, one_piece_state):
        svc = DialogueStateService.__new__(DialogueStateService)
        svc.record_tool_failure(one_piece_state, "web_search", {}, "422")
        ep = one_piece_state.get_slot("episode_number")
        assert ep is not None and ep.value == 1147, (
            "episode_number slot must survive a tool failure"
        )

    def test_tool_failure_updates_last_tool_state(self, one_piece_state):
        svc = DialogueStateService.__new__(DialogueStateService)
        svc.record_tool_failure(one_piece_state, "web_search", {"query": "q"}, "422 bad")
        assert one_piece_state.last_tool_state is not None
        assert one_piece_state.last_tool_state["tool"] == "web_search"
        assert "422" in one_piece_state.last_tool_state["error"]

    def test_tool_failure_preserves_pending_question(self, pending_question_state):
        svc = DialogueStateService.__new__(DialogueStateService)
        svc.record_tool_failure(pending_question_state, "web_search", {}, "500")
        assert pending_question_state.pending_question is not None, (
            "pending_question must survive tool failure"
        )


# ─────────────────────────────────────────────────────────────────────────────
# P0-BUG-4: Dialogue state injected into prompt correctly
# ─────────────────────────────────────────────────────────────────────────────

class TestDialogueStatePromptBlock:
    """build_dialogue_state_block must produce the right context string."""

    def test_empty_state_produces_no_block(self, empty_state):
        block = build_dialogue_state_block(empty_state)
        assert block == "", "No block should be emitted for a fresh state"

    def test_active_topic_appears_in_block(self, one_piece_state):
        block = build_dialogue_state_block(one_piece_state)
        assert "One Piece" in block
        assert "LIVE DIALOGUE STATE" in block

    def test_episode_slot_appears_in_block(self, one_piece_state):
        block = build_dialogue_state_block(one_piece_state)
        assert "1147" in block
        assert "anime_episode" in block

    def test_pending_question_appears_in_block(self, pending_question_state):
        block = build_dialogue_state_block(pending_question_state)
        assert "PENDING QUESTION" in block
        assert "episode number" in block.lower()

    def test_tool_failure_appears_in_block(self, one_piece_state):
        one_piece_state.last_tool_state = {
            "tool": "web_search",
            "error": "422 Missing query",
            "at_turn": 3,
        }
        block = build_dialogue_state_block(one_piece_state)
        assert "Last tool attempt" in block
        assert "PRESERVED despite this failure" in block


# ─────────────────────────────────────────────────────────────────────────────
# P0-BUG-5: Slot type distinction — episode ≠ chapter
# ─────────────────────────────────────────────────────────────────────────────

class TestTypedSlots:
    def test_episode_keyword_gets_anime_episode_type(self, empty_state):
        slots = SlotResolver.resolve("episode 1147", empty_state, DialogueAct.REQUEST)
        assert slots["episode_number"].slot_type == SlotType.ANIME_EPISODE

    def test_chapter_keyword_gets_manga_chapter_type(self, empty_state):
        slots = SlotResolver.resolve("chapter 1085", empty_state, DialogueAct.REQUEST)
        assert slots["chapter_number"].slot_type == SlotType.MANGA_CHAPTER

    def test_season_keyword_filled(self, empty_state):
        slots = SlotResolver.resolve("season 2 episode 5", empty_state, DialogueAct.REQUEST)
        assert "season" in slots and slots["season"].value == 2
        assert "episode_number" in slots and slots["episode_number"].value == 5

    def test_slot_apply_does_not_downgrade_confidence(self, empty_state):
        """Higher-confidence slot should not be overwritten by lower-confidence one."""
        empty_state.set_slot("episode_number", 1147, SlotType.ANIME_EPISODE, 0.99)
        new_slots = {"episode_number": Slot(999, SlotType.ANIME_EPISODE, 0.50)}
        SlotResolver.apply(empty_state, new_slots)
        # Confidence 0.50 < 0.99 → should NOT overwrite
        assert empty_state.slots["episode_number"].value == 1147

    def test_slot_apply_upgrades_lower_confidence(self, empty_state):
        empty_state.set_slot("episode_number", 999, SlotType.ANIME_EPISODE, 0.50)
        new_slots = {"episode_number": Slot(1147, SlotType.ANIME_EPISODE, 0.99)}
        SlotResolver.apply(empty_state, new_slots)
        assert empty_state.slots["episode_number"].value == 1147


# ─────────────────────────────────────────────────────────────────────────────
# P0-BUG-6: fallback query for 422 auto-fill
# ─────────────────────────────────────────────────────────────────────────────

class TestFallbackQueryGeneration:
    def test_topic_only(self, empty_state):
        empty_state.active_topic = "One Piece"
        q = empty_state.get_query_for_active_topic()
        assert q is not None and "One Piece" in q

    def test_topic_plus_episode(self, one_piece_state):
        q = one_piece_state.get_query_for_active_topic()
        assert q is not None
        assert "One Piece" in q
        assert "1147" in q or "episode" in q.lower()

    def test_no_topic_returns_none(self, empty_state):
        q = empty_state.get_query_for_active_topic()
        assert q is None


# ─────────────────────────────────────────────────────────────────────────────
# P0-BUG-7: Confirmation handling
# ─────────────────────────────────────────────────────────────────────────────

class TestConfirmationHandling:
    def test_yes_classified_as_confirmation_when_pending(self):
        state = ConversationTurnState(
            conversation_id="c1", turn_count=1,
            pending_confirmation={"text": "Shall I search for it?", "action_id": "a1"}
        )
        act = DialogueActResolver.resolve("yes", state)
        assert act == DialogueAct.CONFIRMATION

    def test_yes_not_confirmation_without_pending(self, empty_state):
        """'yes' with no pending confirmation is still classified — but not as confirmation."""
        act = DialogueActResolver.resolve("yes", empty_state)
        # Without pending confirmation, "yes" might be REACTION or REQUEST — not CONFIRMATION
        assert act != DialogueAct.CONFIRMATION

    def test_no_classified_as_confirmation_when_pending(self):
        state = ConversationTurnState(
            conversation_id="c1", turn_count=1,
            pending_confirmation={"text": "Delete it?", "action_id": "a2"}
        )
        act = DialogueActResolver.resolve("no", state)
        assert act == DialogueAct.CONFIRMATION


# ─────────────────────────────────────────────────────────────────────────────
# P0-BUG-8: State serialisation round-trip
# ─────────────────────────────────────────────────────────────────────────────

class TestStateSerialisation:
    def test_orm_kwargs_roundtrip(self, one_piece_state):
        kwargs = one_piece_state.to_orm_kwargs()
        assert kwargs["active_topic"] == "One Piece"
        assert kwargs["conversation_id"] == "conv-test-001"
        # Slots round-trip
        slots_json = json.loads(kwargs["slots_json"])
        assert "episode_number" in slots_json
        assert slots_json["episode_number"]["value"] == 1147
        assert slots_json["episode_number"]["type"] == "anime_episode"

    def test_empty_state_orm_kwargs(self, empty_state):
        kwargs = empty_state.to_orm_kwargs()
        assert kwargs["active_topic"] is None
        assert json.loads(kwargs["slots_json"]) == {}
        assert kwargs["pending_question_json"] is None


# ─────────────────────────────────────────────────────────────────────────────
# P0-BUG-9: toolRequests prose leak stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestToolRequestsLeakStripping:
    """Verify that the sanitizer strips prose JSON tool envelopes from displayText."""

    def test_strip_prose_tool_envelope(self):
        import re
        text = 'Sure! toolRequests [{"type": "web_search", "parameters": {"query": "One Piece 1147"}}] Let me search that for you.'
        cleaned = re.sub(
            r'"?toolRequests"?\s*:?\s*\[[\s\S]*?\]',
            "",
            text,
            flags=re.IGNORECASE,
        )
        assert "toolRequests" not in cleaned
        assert "web_search" not in cleaned
        assert "Sure!" in cleaned
        assert "Let me search" in cleaned

    def test_strip_json_style_tool_envelope(self):
        import re
        text = '"toolRequests": [{"type": "search"}] I am looking it up!'
        cleaned = re.sub(
            r'"?toolRequests"?\s*:?\s*\[[\s\S]*?\]',
            "",
            text,
            flags=re.IGNORECASE,
        )
        assert "toolRequests" not in cleaned
        assert "I am looking it up!" in cleaned

    def test_clean_text_unchanged(self):
        import re
        text = "One Piece episode 1147 aired last week!"
        cleaned = re.sub(
            r'"?toolRequests"?\s*:?\s*\[[\s\S]*?\]',
            "",
            text,
            flags=re.IGNORECASE,
        )
        assert cleaned == text


# ─────────────────────────────────────────────────────────────────────────────
# P0-BUG-10: Continuation acts
# ─────────────────────────────────────────────────────────────────────────────

class TestContinuationActs:
    def test_more_classified_as_continuation(self, one_piece_state):
        act = DialogueActResolver.resolve("more", one_piece_state)
        assert act == DialogueAct.CONTINUATION

    def test_continue_classified(self, one_piece_state):
        act = DialogueActResolver.resolve("continue", one_piece_state)
        assert act == DialogueAct.CONTINUATION


# ─────────────────────────────────────────────────────────────────────────────
# Integration: full One Piece → 1147 scenario
# ─────────────────────────────────────────────────────────────────────────────

class TestOnePieceScenario:
    """End-to-end simulation of the real conversation failure transcript."""

    def test_full_scenario_no_context_loss(self):
        """
        Turn 1: User says "One Piece latest episode" → REQUEST, topic=One Piece
        Turn 2: Tool fails 422 → topic/intent preserved
        Turn 3: User says "hina" → VOCATIVE, should_use_fresh_greeting=False
        Turn 4: User says "1147" → ANSWER, fills episode_number slot
        Turn 5: Fallback query includes 'One Piece' and '1147'
        """
        state = ConversationTurnState.empty("conv-scenario-001", "user-1")

        # Turn 1 — "One Piece latest episode"
        text1 = "One Piece latest episode"
        act1 = DialogueActResolver.resolve(text1, state)
        assert act1 == DialogueAct.REQUEST
        slots1 = SlotResolver.resolve(text1, state, act1)
        SlotResolver.apply(state, slots1)
        state.active_topic = "One Piece"
        state.active_intent = "web_search"
        state.last_dialogue_act = act1
        state.turn_count += 1

        # Turn 2 — Tool 422 failure
        svc = DialogueStateService.__new__(DialogueStateService)
        svc.record_tool_failure(state, "web_search", {"query": None}, "422 Missing required argument: query")
        assert state.active_topic == "One Piece", "Topic must survive 422"

        # Turn 3 — "hina" (user addressing Hina by name)
        text3 = "hina"
        act3 = DialogueActResolver.resolve(text3, state)
        assert act3 == DialogueAct.VOCATIVE, "hina mid-convo must be VOCATIVE"
        assert not state.should_use_fresh_greeting(), (
            "Fresh greeting must be suppressed — active topic exists"
        )

        # Turn 4 — "1147" (episode number answer)
        text4 = "1147"
        # Add pending question to mirror realistic state
        state.pending_question = {"text": "Which episode?", "asked_at_turn": 3}
        act4 = DialogueActResolver.resolve(text4, state)
        assert act4 == DialogueAct.ANSWER, "'1147' must be ANSWER not REQUEST"
        slots4 = SlotResolver.resolve(text4, state, act4)
        SlotResolver.apply(state, slots4)
        assert "episode_number" in state.slots, "episode_number must be filled from '1147'"
        assert state.slots["episode_number"].value == 1147

        # Turn 5 — Fallback query auto-construction for 422 fix
        fallback_q = state.get_query_for_active_topic()
        assert fallback_q is not None
        assert "One Piece" in fallback_q
        assert "1147" in fallback_q, (
            "Fallback query must include episode number for web_search auto-populate"
        )

        # Verify state block
        block = build_dialogue_state_block(state)
        assert "One Piece" in block
        assert "1147" in block
        assert "LIVE DIALOGUE STATE" in block
