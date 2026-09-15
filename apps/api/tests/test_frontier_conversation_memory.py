from __future__ import annotations

from hinaa_api.models import TurnRequest


def _seed_conversation(memory_service, owner: str) -> str:
    conversation_id = None
    turns = [
        (
            "Create a cinematic character girl named Asha with pink cyberpunk hair.",
            "Asha is set as the main character.",
            [{"asset_id": "asset_face_001", "kind": "image", "filename": "asha-face.png", "role": "reference"}],
        ),
        ("Use this as the main face reference.", "Approved asset_face_001 as the face reference.", []),
        ("Make a neon rainy street scene for her.", "Scene task is planned.", []),
        ("Reject the cartoon version, keep it photorealistic.", "Cartoon style rejected.", []),
        ("Create a polished poster for the same girl.", "Poster task remains open.", []),
        ("Now continue the poster and keep her face like before.", "Continuity state updated.", []),
    ]
    for user_text, assistant_text, attachments in turns:
        conversation_id = memory_service.append_turn(
            user_id=owner,
            companion_id="hinaa",
            conversation_id=conversation_id,
            user_text=user_text,
            assistant_text=assistant_text,
            language="mixed",
            attachments=attachments,
        )
    assert conversation_id is not None
    return conversation_id


def test_durable_working_context_keeps_exact_recent_turns_and_structured_state(client):
    owner = client.get("/v1/workspace/identity").json()["userId"]
    memory_service = client.app.state.memory_service
    conversation_id = _seed_conversation(memory_service, owner)

    context = memory_service.recent_working_context(owner, conversation_id, limit=4)

    assert [message["role"] for message in context["recentMessages"]][-2:] == ["user", "assistant"]
    assert "Now continue the poster" in context["recentMessages"][-2]["content"]
    assert context["rollingSummary"]["current_goal"]
    assert any(entity["displayName"] == "Asha" for entity in context["entities"])
    assert any(entity["assetId"] == "asset_face_001" for entity in context["entities"])
    assert any(event["type"] == "rejection" for event in context["episodicEvents"])


def test_reference_resolution_targets_previous_entity_asset_and_unfinished_task(client):
    owner = client.get("/v1/workspace/identity").json()["userId"]
    memory_service = client.app.state.memory_service
    conversation_id = _seed_conversation(memory_service, owner)

    resolved = memory_service.resolve_reference_intent(
        owner,
        conversation_id,
        "continue and make her like the previous one",
    )

    assert resolved["hasReference"] is True
    assert resolved["intent"] in {"continue_task", "modify_previous"}
    assert resolved["targetEntity"]["displayName"] in {"Asha", "asha-face.png"}
    assert resolved["targetAsset"]["asset_id"] == "asset_face_001"
    assert resolved["unfinishedTask"]["goal"]
    assert resolved["resolutionSource"]["recentMessages"] is True
    assert resolved["resolutionSource"]["rollingSummary"] is True


def test_conversation_context_and_resolution_routes_are_owner_scoped(client):
    owner = client.get("/v1/workspace/identity", headers={"X-HINAA-Dev-User": "alice"}).json()["userId"]
    memory_service = client.app.state.memory_service
    conversation_id = _seed_conversation(memory_service, owner)

    ok = client.get(
        f"/v1/conversations/{conversation_id}/working-context",
        headers={"X-HINAA-Dev-User": "alice"},
    )
    assert ok.status_code == 200
    assert ok.json()["conversationId"] == conversation_id

    denied = client.get(
        f"/v1/conversations/{conversation_id}/working-context",
        headers={"X-HINAA-Dev-User": "bob"},
    )
    assert denied.status_code == 404

    resolved = client.post(
        f"/v1/conversations/{conversation_id}/resolve-reference",
        headers={"X-HINAA-Dev-User": "alice"},
        json={"text": "redo it like before"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["hasReference"] is True


def test_conversation_service_compiles_durable_history_and_reference_blocks(client):
    owner = client.get("/v1/workspace/identity").json()["userId"]
    memory_service = client.app.state.memory_service
    conversation_id = _seed_conversation(memory_service, owner)
    service = client.app.state.service

    history, blocks = service._durable_conversation_context(
        TurnRequest(
            sessionId=conversation_id,
            conversationId=conversation_id,
            text="continue and make her like before",
            providerMode="mock",
        ),
        owner,
    )

    assert any("Asha" in content for _, content in history)
    assert any(block.startswith("conversation_state:") for block in blocks)
    assert any(block.startswith("reference_resolution:") for block in blocks)


def test_turns_create_offline_training_candidates_not_online_training(client):
    owner = client.get("/v1/workspace/identity", headers={"X-HINAA-Dev-User": "alice"}).json()["userId"]
    memory_service = client.app.state.memory_service
    conversation_id = _seed_conversation(memory_service, owner)

    candidates = memory_service.list_training_candidates(owner)

    assert candidates
    assert candidates[0]["status"] == "pending_review"
    assert candidates[0]["metadata"]["training_policy"] == "offline_review_required"
    assert candidates[0]["metadata"]["online_weight_update"] is False
    assert candidates[0]["conversationId"] == conversation_id

    response = client.get("/v1/training/candidates", headers={"X-HINAA-Dev-User": "alice"})
    assert response.status_code == 200
    assert response.json()["onlineTraining"] is False
    assert response.json()["candidates"]

    denied = client.get("/v1/training/candidates", headers={"X-HINAA-Dev-User": "bob"})
    assert denied.status_code == 200
    assert denied.json()["candidates"] == []
