from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.main import create_app
from hinaa_api.models import TurnRequest
from hinaa_api.persistence import MemoryService, init_db
from hinaa_api.persistence.db import reset_session_factory
from hinaa_api.services import ConversationService


def _app_client() -> TestClient:
    reset_session_factory()
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        GEMINI_API_KEY="",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        _env_file=None,
    )
    return TestClient(create_app(settings))


def test_remember_list_forget_and_isolation() -> None:
    with _app_client() as client:
        created = client.post(
            "/v1/privacy/memories",
            headers={"X-HINAA-Dev-User": "alice"},
            json={"content": "I prefer Romanized Nepali replies", "category": "preference"},
        )
        assert created.status_code == 200
        memory_id = created.json()["id"]
        listed = client.get("/v1/privacy/memories", headers={"X-HINAA-Dev-User": "alice"})
        assert listed.status_code == 200
        assert len(listed.json()["memories"]) == 1
        bob_list = client.get("/v1/privacy/memories", headers={"X-HINAA-Dev-User": "bob"})
        assert bob_list.json()["memories"] == []
        forgotten = client.delete(
            f"/v1/privacy/memories/{memory_id}",
            headers={"X-HINAA-Dev-User": "alice"},
        )
        assert forgotten.json()["forgotten"] is True
        assert (
            client.get("/v1/privacy/memories", headers={"X-HINAA-Dev-User": "alice"}).json()[
                "memories"
            ]
            == []
        )


def test_sensitive_and_disabled_memory_blocked() -> None:
    with _app_client() as client:
        headers = {"X-HINAA-Dev-User": "carol"}
        blocked = client.post(
            "/v1/privacy/memories",
            headers=headers,
            json={"content": "my api key is sk-test-123"},
        )
        assert blocked.status_code == 422
        client.patch("/v1/privacy/memory", headers=headers, json={"enabled": False})
        disabled = client.post(
            "/v1/privacy/memories",
            headers=headers,
            json={"content": "I like tea"},
        )
        assert disabled.status_code == 409


def test_export_and_delete_all() -> None:
    with _app_client() as client:
        headers = {"X-HINAA-Dev-User": "dana"}
        client.post(
            "/v1/privacy/memories",
            headers=headers,
            json={"content": "Favorite subject is physics"},
        )
        export = client.get("/v1/privacy/export", headers=headers)
        assert export.status_code == 200
        assert export.json()["memoryEnabled"] is True
        deleted = client.delete("/v1/privacy/account", headers=headers)
        assert deleted.json()["deleted"] is True


def test_service_level_cross_user_forget_fails() -> None:
    reset_session_factory()
    factory = init_db(
        Settings(
            HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
            _env_file=None,
        )
    )
    service = MemoryService(factory)
    a = service.ensure_user("a")
    b = service.ensure_user("b")
    memory = service.remember(a.id, "I study Nepali")
    try:
        service.forget(b.id, str(memory["id"]))
        raise AssertionError("cross-user forget should fail")
    except HinaaError as error:
        assert error.code == "MEMORY_NOT_FOUND"


def test_self_learned_facts_persist_to_durable_store_via_turn() -> None:
    """A conversation turn that reveals facts stores them durably for that user."""
    with _app_client() as client:
        headers = {"X-HINAA-Dev-User": "prabin"}
        response = client.post(
            "/v1/conversations/turns:stream",
            headers=headers,
            json={
                "sessionId": "learn-facts",
                "text": "My name is Prabin and I love coding",
                "companionId": "hinaa",
                "language": "mixed",
                "providerMode": "mock",
            },
        )
        assert response.status_code == 200
        listed = client.get("/v1/privacy/memories", headers=headers)
        assert listed.status_code == 200
        contents = [memory["content"] for memory in listed.json()["memories"]]
        assert any("Prabin" in content for content in contents)
        assert any("coding" in content for content in contents)


def test_durable_memories_survive_restart_and_are_recalled() -> None:
    """Learned facts persist across a service restart and feed later prompts."""
    reset_session_factory()
    factory = init_db(
        Settings(
            HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
            _env_file=None,
        )
    )
    service = MemoryService(factory)
    user = service.ensure_user("prabin")

    async def run_turn(conversation: ConversationService, session_id: str) -> None:
        await conversation.create_plan(
            TurnRequest(
                sessionId=session_id,
                text="My name is Prabin and I love coding",
                companionId="hinaa",
                language="mixed",
                providerMode="mock",
            ),
            user_id=user.id,
        )

    # First process lifetime: fact is learned ephemerally and pushed durably.
    first_life = ConversationService(Settings(HINAA_PROVIDER_MODE="mock", _env_file=None), memory_service=service)
    asyncio.run(run_turn(first_life, "session-one"))
    assert any("Prabin" in block for block in service.approved_memory_blocks(user.id))

    # Restart: a fresh ConversationService (empty SessionMemory) over the same
    # durable store must still recall the fact for prompt injection.
    second_life = ConversationService(
        Settings(HINAA_PROVIDER_MODE="mock", _env_file=None), memory_service=service
    )
    approved = second_life._approved_blocks(user.id)
    assert any("Prabin" in block for block in approved)
    # And the fact must not be re-stored as a duplicate after the restart.
    asyncio.run(run_turn(second_life, "session-two"))
    memories = service.list_memories(user.id)
    assert sum("Prabin" in memory["content"] for memory in memories) == 1


def test_disabled_memory_does_not_break_turns_or_store_facts() -> None:
    with _app_client() as client:
        headers = {"X-HINAA-Dev-User": "quiet"}
        client.patch("/v1/privacy/memory", headers=headers, json={"enabled": False})
        response = client.post(
            "/v1/conversations/turns:stream",
            headers=headers,
            json={
                "sessionId": "no-memory",
                "text": "My name is Quiet and I love silence",
                "companionId": "hinaa",
                "language": "mixed",
                "providerMode": "mock",
            },
        )
        assert response.status_code == 200
        listed = client.get("/v1/privacy/memories", headers=headers)
        assert listed.json()["memories"] == []
