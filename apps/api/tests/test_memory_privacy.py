from __future__ import annotations

import asyncio
import json
import socket

from fastapi.testclient import TestClient

from hinaa_api.circuit_breaker import reset_circuit_breakers
from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.main import create_app
from hinaa_api.models import TurnRequest
from hinaa_api.persistence import MemoryService, init_db
from hinaa_api.persistence.db import reset_session_factory
from hinaa_api.services import ConversationService


def _app_client(**overrides) -> TestClient:
    reset_session_factory()
    # Every brain is switched off unless the test turns one on explicitly: this
    # machine exports real keys, and a stray credential would silently answer a
    # turn that is supposed to fail.
    settings = {
        "HINAA_PROVIDER_MODE": "mock",
        "AZURE_SPEECH_KEY": "",
        "AZURE_SPEECH_REGION": "",
        "GEMINI_API_KEY": "",
        "GROQ_API_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENAI_CODEX_API_KEY": "",
        "OPENAI_CODEX_BASE_URL": "",
        "AGENT_ROUTER_API_KEY": "",
        "AGENT_ROUTER_BASE_URL": "",
        "CX_GATEWAY_API_KEY": "",
        "CX_GATEWAY_BASE_URL": "",
        "HINAA_CLAUDE_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "ELEVENLABS_API_KEY": "",
        "HINAA_DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "HINAA_AUTH_MODE": "dev",
        "HINAA_PERSISTENCE_ENABLED": True,
    }
    settings.update(overrides)
    return TestClient(create_app(Settings(**settings, _env_file=None)))


def _closed_port_url() -> str:
    """A real socket nobody is listening on, so the brain fails for real."""
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return f"http://127.0.0.1:{port}/v1"


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


def test_privacy_routes_refuse_anonymous_callers() -> None:
    """The public URL used to answer these as the owner with no credential at all."""
    with _app_client() as client:
        for path in ("/v1/privacy/status", "/v1/privacy/memories", "/v1/privacy/export"):
            anonymous = client.get(path)
            assert anonymous.status_code == 401, path
            assert anonymous.json()["code"] == "AUTH_REQUIRED", path


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


def test_a_dead_brain_still_learns_what_he_told_her() -> None:
    """He reported it as "she cannot lock and learn". Extraction and the durable
    write both ran after the provider returned, so a turn whose brain was
    unreachable raised straight past them and the facts were dropped.

    The brain here is a socket nobody is listening on, because the bug lives
    only on a genuine failure path -- and the proof is the store read back
    through the memory endpoint, not a call count.
    """
    reset_circuit_breakers()
    try:
        with _app_client(
            CX_GATEWAY_API_KEY="test-cx-key",
            CX_GATEWAY_BASE_URL=_closed_port_url(),
        ) as client:
            headers = {"X-HINAA-Dev-User": "dead-brain"}
            response = client.post(
                "/v1/conversations/turns:stream",
                headers=headers,
                json={
                    "sessionId": "learn-while-blind",
                    "text": (
                        "My name is Prabin and I love coding. "
                        "Remember that the studio rent is due on the 3rd."
                    ),
                    "companionId": "hinaa",
                    "language": "mixed",
                    "providerMode": "cx-gateway",
                },
            )
            assert response.status_code == 200
            events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
            assert any(event.get("type") == "error" for event in events), events
            assert [e for e in events if e.get("type") == "plan"] == [], "the brain must not answer"

            listed = client.get("/v1/privacy/memories", headers=headers)
            contents = [memory["content"] for memory in listed.json()["memories"]]
    finally:
        reset_circuit_breakers()

    assert any("Prabin" in content for content in contents), contents
    assert any("coding" in content for content in contents), contents
    assert any("studio rent is due on the 3rd" in content for content in contents), contents


def test_restating_a_memory_never_crashes_the_store() -> None:
    """Measured through the real endpoints: rewording one memory into text she
    had held before, or into text another memory already says, raised
    IntegrityError out of the unique index on (user_id, normalized_hash) and the
    request died as a 500 with both rows left as they were."""
    with _app_client() as client:
        headers = {"X-HINAA-Dev-User": "restate"}
        held = client.post(
            "/v1/privacy/memories",
            headers=headers,
            json={"content": "My cat is called Momo", "category": "fact"},
        ).json()
        live = client.post(
            "/v1/privacy/memories",
            headers=headers,
            json={"content": "My cat is called Kiko", "category": "fact"},
        ).json()
        current = [m["content"] for m in client.get("/v1/privacy/memories", headers=headers).json()["memories"]]
        assert sorted(current) == sorted(["My cat is called Momo", "My cat is called Kiko"])

        # She forgot one wording, then he restates the other memory as it.
        client.delete(f"/v1/privacy/memories/{held['id']}", headers=headers)
        back = client.post(
            f"/v1/privacy/memories/{live['id']}/supersede",
            headers=headers,
            json={"content": "My cat is called Momo", "category": "fact"},
        )
        assert back.status_code == 200, back.text
        revived = [
            m
            for m in client.get("/v1/privacy/memories", headers=headers).json()["memories"]
            if "Momo" in m["content"]
        ]
        assert len(revived) == 1, revived
        assert revived[0]["id"] == held["id"], "the row she already owned must be reused"
        assert revived[0]["status"] == "approved", revived[0]

        # Rewording a memory into text another live memory says must not insert
        # a second owner of that hash either.
        third = client.post(
            "/v1/privacy/memories",
            headers=headers,
            json={"content": "I study in the library", "category": "goal"},
        ).json()
        merged = client.post(
            f"/v1/privacy/memories/{third['id']}/supersede",
            headers=headers,
            json={"content": "My cat is called Momo", "category": "fact"},
        )
        assert merged.status_code == 200, merged.text
        momo = [
            m
            for m in client.get("/v1/privacy/memories", headers=headers).json()["memories"]
            if "Momo" in m["content"]
        ]
        assert len(momo) == 1, momo


def test_an_edited_memory_is_found_by_its_new_words() -> None:
    """Editing a memory in place used to leave its dedupe hash pointing at the
    old sentence, so telling her the new wording afterwards stored a second copy
    of the same fact."""
    with _app_client() as client:
        headers = {"X-HINAA-Dev-User": "rehash"}
        created = client.post(
            "/v1/privacy/memories",
            headers=headers,
            json={"content": "My favourite fruit is mango", "category": "preference"},
        ).json()
        edited = client.put(
            f"/v1/privacy/memories/{created['id']}",
            headers=headers,
            json={"content": "My favourite fruit is jackfruit"},
        )
        assert edited.status_code == 200, edited.text

        again = client.post(
            "/v1/privacy/memories",
            headers=headers,
            json={"content": "My favourite fruit is jackfruit", "category": "preference"},
        )
        assert again.status_code == 200, again.text
        assert again.json()["id"] == edited.json()["id"], "the edit must be findable by its new text"
        rows = [
            m
            for m in client.get("/v1/privacy/memories", headers=headers).json()["memories"]
            if "fruit" in m["content"]
        ]
        assert len(rows) == 1, rows


def test_a_forgotten_fact_can_be_learned_again() -> None:
    """The other half of "she cannot lock and learn". He told her the same thing
    twice with a delete in between and the second time nothing was stored:
    ``forget`` soft-deletes, so the row stays and keeps its place in the unique
    index on (user_id, normalized_hash). The re-learn then tried to INSERT a
    second row for the same hash and raised IntegrityError, which the persist
    loop swallows -- so the fact was unlearnable forever after one deletion.
    """
    text = "Remember that my cat is called Momo and she is exactly two years old."

    def turn(client: TestClient, headers: dict, session_id: str) -> None:
        response = client.post(
            "/v1/conversations/turns:stream",
            headers=headers,
            json={
                "sessionId": session_id,
                "text": text,
                "companionId": "hinaa",
                "language": "mixed",
                "providerMode": "mock",
            },
        )
        assert response.status_code == 200

    def momo_rows(client: TestClient, headers: dict) -> list[dict]:
        listed = client.get("/v1/privacy/memories", headers=headers)
        return [m for m in listed.json()["memories"] if "Momo" in m["content"]]

    with _app_client() as client:
        headers = {"X-HINAA-Dev-User": "relearn"}
        turn(client, headers, "relearn-first")
        first = momo_rows(client, headers)
        assert len(first) == 1, first

        deleted = client.delete(f"/v1/privacy/memories/{first[0]['id']}", headers=headers)
        assert deleted.status_code == 200
        assert momo_rows(client, headers) == [], "she must really have forgotten it"

        turn(client, headers, "relearn-second")
        again = momo_rows(client, headers)

    assert len(again) == 1, f"re-learning a forgotten fact stored {len(again)} rows"
    assert again[0]["status"] == "approved", again[0]


def test_she_only_claims_a_memory_she_can_actually_keep() -> None:
    """The prompt is told the truth by this predicate, so bind it to the two
    real reasons a fact cannot survive a turn: no signed-in owner to store it
    under, and no store to write it to."""
    reset_session_factory()
    store = MemoryService(
        init_db(
            Settings(
                HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
                _env_file=None,
            )
        )
    )
    owner = store.ensure_user("owner-two")
    settings = Settings(HINAA_PROVIDER_MODE="mock", _env_file=None)
    request = TurnRequest(
        sessionId="claim-check",
        text="remember that my studio rent is due on the 3rd",
        companionId="hinaa",
        language="mixed",
        providerMode="mock",
    )

    with_store = ConversationService(settings, memory_service=store)
    assert with_store._capture_turn_facts(request, owner.id) is True
    assert any(
        "3rd" in memory["content"] for memory in store.list_memories(owner.id)
    ), "the true case must really write the row it promised"
    assert with_store._capture_turn_facts(request, None) is False

    no_store = ConversationService(settings)
    assert no_store._capture_turn_facts(request, owner.id) is False


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


def test_resolve_user_accepts_an_id_without_minting_a_second_identity() -> None:
    """durable_tasks.owner_id references users.id, and an unauthenticated tool
    call supplies the auth subject instead — the insert failed its foreign key
    and /tools/execute answered 502, so searched images never rendered. The
    resolver must take either form without splitting one person in two."""
    reset_session_factory()
    factory = init_db(
        Settings(
            HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
            _env_file=None,
        )
    )
    service = MemoryService(factory)

    resolved = service.resolve_user("local-dev-user")
    assert service.resolve_user(resolved.id).id == resolved.id
    assert service.resolve_user("local-dev-user").id == resolved.id

    from sqlalchemy import func, select
    from hinaa_api.persistence.orm import User

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
