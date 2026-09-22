from __future__ import annotations

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.models import AssistantTurnPlan, ToolRequest
from hinaa_api.services import ConversationService

import pytest


@pytest.fixture
def settings() -> Settings:
    return Settings(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        GEMINI_API_KEY="",
        _env_file=None,
    )


class FakeMemoryService:
    def __init__(self, stored=None, remember_error: HinaaError | None = None) -> None:
        self.stored = stored if stored is not None else []
        self.remember_error = remember_error
        self.saved: list[tuple[str, str]] = []
        self.forgotten: list[str] = []

    def remember(self, *, user_id: str, content: str, category: str = "other", **_kwargs):
        if self.remember_error is not None:
            raise self.remember_error
        self.saved.append((user_id, content))
        return {"id": f"mem-{len(self.saved)}", "content": content, "category": category}

    def list_memories(self, user_id: str):
        return list(self.stored)

    def forget(self, user_id: str, memory_id: str):
        self.forgotten.append(memory_id)
        return {"id": memory_id, "status": "revoked"}


def _plan(toolRequests: list[ToolRequest] | None = None) -> AssistantTurnPlan:
    return AssistantTurnPlan(
        spokenText="Got it, babe! I've saved that.",
        displayText="Got it, babe! I've saved that.",
        language="mixed",
        emotion={"primary": "happy", "intensity": 0.5, "valence": 0.5, "arousal": 0.3},
        performance={
            "facePreset": "soft_smile",
            "gesture": "none",
            "gazeTarget": "camera",
            "headMotion": "none",
            "blinkRate": 0.45,
        },
        memoryCandidates=[],
        toolRequests=toolRequests or [],
    )


def _run(text: str, service: ConversationService) -> AssistantTurnPlan:
    plan = _plan()
    service._inject_deterministic_tool_intents(text, plan, user_id="user-1")
    return plan


def test_memory_save_writes_the_durable_store_and_names_the_saved_text(settings: Settings) -> None:
    memory = FakeMemoryService()
    plan = _run("/memory save my favourite colour is teal", ConversationService(settings, memory_service=memory))

    assert memory.saved == [("user-1", "my favourite colour is teal")]
    assert plan.displayText == "Saved to your memories: my favourite colour is teal"
    assert plan.toolRequests == []


def test_memory_save_without_a_store_reports_not_configured(settings: Settings) -> None:
    plan = _run("/memory save my favourite colour is teal", ConversationService(settings))

    assert plan.displayText == "Memories are not stored on this HINAA instance, so I could not do that."
    assert plan.toolRequests == []


def test_memory_save_carries_the_refusal_reason_instead_of_claiming_success(settings: Settings) -> None:
    memory = FakeMemoryService(
        remember_error=HinaaError("MEMORY_DISABLED", "Memory is disabled.", 409, True)
    )
    plan = _run("/memory save my favourite colour is teal", ConversationService(settings, memory_service=memory))

    assert memory.saved == []
    assert plan.displayText == "I did not save that: Memory is disabled."


def test_memory_save_requires_an_owner_before_touching_the_store(settings: Settings) -> None:
    memory = FakeMemoryService(stored=[{"id": "mem-1", "content": "my favourite colour is teal"}])
    plan = _plan()
    ConversationService(settings, memory_service=memory)._inject_deterministic_tool_intents(
        "/memory save my favourite colour is teal", plan
    )

    assert memory.saved == []
    assert "no signed-in owner" in plan.displayText
    assert plan.toolRequests == []


def test_memory_recall_lists_only_the_entries_that_match(settings: Settings) -> None:
    memory = FakeMemoryService(
        stored=[
            {"id": "mem-1", "content": "my favourite colour is teal"},
            {"id": "mem-2", "content": "prefers late-night work blocks"},
        ]
    )
    plan = _run("/memory recall colour", ConversationService(settings, memory_service=memory))

    assert "my favourite colour is teal" in plan.displayText
    assert "prefers late-night work blocks" not in plan.displayText
    assert plan.toolRequests == []


def test_memory_forget_needs_one_unambiguous_match(settings: Settings) -> None:
    memory = FakeMemoryService(
        stored=[
            {"id": "mem-1", "content": "teal is my favourite colour"},
            {"id": "mem-2", "content": "teal curtains for the studio"},
        ]
    )
    plan = _run("/memory forget teal", ConversationService(settings, memory_service=memory))

    assert memory.forgotten == []
    assert "removed none" in plan.displayText

    single = FakeMemoryService(stored=[{"id": "mem-9", "content": "curtains are teal"}])
    plan = _run("/memory forget curtains are teal", ConversationService(settings, memory_service=single))

    assert single.forgotten == ["mem-9"]
    assert plan.displayText == "Removed from your memories: curtains are teal"


def test_commands_without_a_registered_handler_stop_proposing_actions(settings: Settings) -> None:
    service = ConversationService(settings)
    for text in ("/settings open", "/model gemini", "/avatar change", "/automate daily summary"):
        plan = _run(text, service)
        assert plan.toolRequests == [], text


def test_play_still_reaches_the_registered_player(settings: Settings) -> None:
    plan = _run("/play lofi beats", ConversationService(settings))

    assert [request.toolName for request in plan.toolRequests] == ["youtube_playback_request"]
    assert plan.toolRequests[0].parameters == {"query": "lofi beats"}
