from __future__ import annotations

import asyncio

from hinaa_api.dialogue_state import (
    AssetReferenceResolver,
    AssetSelectionSource,
    ConversationTurnState,
)
from hinaa_api.models import TurnRequest


def _state_with_gallery() -> ConversationTurnState:
    state = ConversationTurnState.empty("p010-convo", "user-1")
    state.active_entities = [{"type": "character", "name": "Mikasa Ackerman"}]
    state.active_topic = "Mikasa Ackerman"
    state.tool_result_sets = [{
        "result_set_id": "RS_MIKASA",
        "tool": "image_search",
        "query": "Mikasa Ackerman Attack on Titan",
        "canonical_subject": "Mikasa Ackerman",
        "entity_ids": ["mikasa_ackerman"],
        "ordered_asset_ids": ["IMG_A", "IMG_B", "IMG_C", "IMG_D"],
        "thumbnail_uris": ["/thumb/a", "/thumb/b", "/thumb/c", "/thumb/d"],
        "source_uris": ["/src/a", "/src/b", "/src/c", "/src/d"],
    }]
    return state


def test_ordinal_second_one_selects_exact_second_asset_and_trace():
    state = _state_with_gallery()

    trace = AssetReferenceResolver.resolve_with_trace("second one", state)

    assert trace is not None
    assert trace["target_id"] == "IMG_B"
    assert trace["ordinalIndex"] == 1
    assert trace["selectedResultSet"] == "RS_MIKASA"
    assert state.selected_asset is not None
    assert state.selected_asset["asset_id"] == "IMG_B"
    assert state.selected_asset["selection_source"] == "ORDINAL_REFERENCE"


def test_ui_click_selection_wins_for_deictic_use_this():
    state = _state_with_gallery()
    selection = AssetReferenceResolver.select_asset(
        state,
        result_set_id="RS_MIKASA",
        asset_id="IMG_C",
        ordinal_index=2,
        source=AssetSelectionSource.UI_CLICK,
    )

    assert selection["asset_id"] == "IMG_C"
    assert AssetReferenceResolver.resolve_asset_id("use this one", state) == "IMG_C"
    assert AssetReferenceResolver.resolve_asset_id("same one but darker", state) == "IMG_C"


def test_multi_entity_ordinal_uses_named_result_set_not_most_recent():
    state = _state_with_gallery()
    state.tool_result_sets.append({
        "result_set_id": "RS_NARUTO",
        "tool": "image_search",
        "query": "Naruto Uzumaki Naruto",
        "canonical_subject": "Naruto Uzumaki",
        "entity_ids": ["naruto_uzumaki"],
        "ordered_asset_ids": ["NAR_A", "NAR_B", "NAR_C"],
    })

    trace = AssetReferenceResolver.resolve_with_trace("second Mikasa one", state)

    assert trace is not None
    assert trace["target_id"] == "IMG_B"
    assert trace["selectedResultSet"] == "RS_MIKASA"


def test_selection_rejects_diverged_frontend_order():
    state = _state_with_gallery()

    try:
        AssetReferenceResolver.select_asset(
            state,
            result_set_id="RS_MIKASA",
            asset_id="IMG_C",
            ordinal_index=1,
            source=AssetSelectionSource.UI_CLICK,
        )
    except ValueError as error:
        assert "ordinal_index" in str(error)
    else:
        raise AssertionError("selection should reject order mismatch")


def test_http_selection_persists_and_restores_after_reload(client):
    owner = client.get("/v1/workspace/identity", headers={"X-HINAA-Dev-User": "p010"}).json()["userId"]
    service = client.app.state.service
    state = _state_with_gallery()
    state.conversation_id = "p010-http"
    state.user_id = owner
    service.dialogue_state_service.save(state)

    response = client.post(
        "/v1/conversations/p010-http/assets/select",
        headers={"X-HINAA-Dev-User": "p010"},
        json={"resultSetId": "RS_MIKASA", "assetId": "IMG_B", "index": 1, "source": "UI_CLICK"},
    )

    assert response.status_code == 200
    assert response.json()["selection"]["asset_id"] == "IMG_B"

    restored = client.get(
        "/v1/conversations/p010-http/assets/selection",
        headers={"X-HINAA-Dev-User": "p010"},
    )
    assert restored.status_code == 200
    assert restored.json()["selection"]["asset_id"] == "IMG_B"


def test_selected_asset_is_used_as_generation_reference(client):
    owner = client.get("/v1/workspace/identity", headers={"X-HINAA-Dev-User": "p010-gen"}).json()["userId"]
    service = client.app.state.service
    state = _state_with_gallery()
    state.conversation_id = "p010-generate"
    state.user_id = owner
    AssetReferenceResolver.select_asset(
        state,
        result_set_id="RS_MIKASA",
        asset_id="IMG_B",
        ordinal_index=1,
        source=AssetSelectionSource.UI_CLICK,
    )
    service.dialogue_state_service.save(state)

    result = asyncio.run(service.create_plan(
        TurnRequest(
            sessionId="p010-generate",
            conversationId="p010-generate",
            text="generate her using this image",
            providerMode="mock",
        ),
        user_id=owner,
    ))

    req = next(t for t in result.value.toolRequests if t.toolName == "image_generate")
    assert req.parameters["reference_images"] == ["IMG_B"]
    assert req.parameters["reference_asset_id"] == "IMG_B"
    assert req.parameters["subject_entity"] == "Mikasa Ackerman"


def test_same_one_but_darker_preserves_reference_lineage(client):
    owner = client.get("/v1/workspace/identity", headers={"X-HINAA-Dev-User": "p010-dark"}).json()["userId"]
    service = client.app.state.service
    state = _state_with_gallery()
    state.conversation_id = "p010-dark"
    state.user_id = owner
    AssetReferenceResolver.select_asset(
        state,
        result_set_id="RS_MIKASA",
        asset_id="IMG_B",
        ordinal_index=1,
        source=AssetSelectionSource.UI_CLICK,
    )
    service.dialogue_state_service.save(state)

    result = asyncio.run(service.create_plan(
        TurnRequest(
            sessionId="p010-dark",
            conversationId="p010-dark",
            text="same one but darker",
            providerMode="mock",
        ),
        user_id=owner,
    ))

    req = next(t for t in result.value.toolRequests if t.toolName == "image_generate")
    assert req.parameters["reference_images"] == ["IMG_B"]
    assert "darker" in req.parameters["prompt"].lower()
