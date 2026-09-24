from __future__ import annotations

import asyncio
import pytest

from hinaa_api.config import Settings
from hinaa_api.models import TurnRequest
from hinaa_api.services import ConversationService
from hinaa_api.media.search_intelligence import (
    TopicTransition,
    detect_topic_transition,
    build_media_intent,
    compile_image_search_query,
    verify_image_results,
)


def test_topic_transition_detector_identifies_explicit_switch():
    """Detects that introducing a new location/event like 'Nepal current incident' is an EXPLICIT_SWITCH."""
    transition = detect_topic_transition(
        "Now fetch Nepal current incident images",
        active_topic="Mikasa Ackerman",
        active_entities=[{"type": "character", "name": "Mikasa Ackerman"}],
    )
    assert transition == TopicTransition.EXPLICIT_SWITCH


def test_topic_transition_detector_identifies_same_topic_for_deictic_reference():
    """Detects that 'show more of her' or 'fetch them' is SAME_TOPIC."""
    transition1 = detect_topic_transition(
        "show more of her",
        active_topic="Mikasa Ackerman",
        active_entities=[{"type": "character", "name": "Mikasa Ackerman"}],
    )
    assert transition1 == TopicTransition.SAME_TOPIC

    transition2 = detect_topic_transition(
        "fetch them",
        active_topic="Mikasa Ackerman",
        active_entities=[{"type": "character", "name": "Mikasa Ackerman"}],
    )
    assert transition2 == TopicTransition.SAME_TOPIC


def test_build_media_intent_explicit_nepal_overrides_stale_mikasa():
    """An explicit current-event request must NEVER resolve to stale active anime character."""
    intent = build_media_intent(
        "Now fetch Nepal current incident images",
        active_subject="Mikasa Ackerman",
    )
    assert intent is not None
    assert "mikasa" not in intent.canonical_subject.lower()
    assert "ackerman" not in intent.canonical_subject.lower()
    assert "nepal" in intent.canonical_subject.lower()
    assert intent.subject_type in ("event", "location", "topic", "current_event")


def test_build_media_intent_deictic_uses_active_subject():
    """Referential follow-ups ('show more', 'fetch them', 'her') must resolve to active subject."""
    intent = build_media_intent(
        "show more of her",
        active_subject="Mikasa Ackerman",
    )
    assert intent is not None
    assert intent.canonical_subject == "Mikasa Ackerman"


def test_current_event_query_compiles_without_anime_and_sets_general_web():
    """Current event image search compiles to photojournalism query and excludes anime/booru."""
    intent = build_media_intent(
        "fetch Nepal current incident images",
        active_subject="Mikasa Ackerman",
    )
    assert intent is not None
    spec = compile_image_search_query(intent)

    assert "attack on titan" not in spec.primary_query.lower()
    assert "mikasa" not in spec.primary_query.lower()
    assert "nepal" in spec.primary_query.lower()
    assert spec.provider_profile in ("general_web_image_search", "news_image_search")
    assert any("anime" in neg for neg in spec.negative_terms)


def test_media_topic_consistency_verifier_rejects_anime_for_real_world_event():
    """Verifies that an anime character result is rejected if searching for a real-world event."""
    intent = build_media_intent("fetch Nepal current incident images")
    assert intent is not None
    spec = compile_image_search_query(intent)

    candidates = [
        {
            "id": "1",
            "title": "Mikasa Ackerman official anime illustration",
            "snippet": "Attack on Titan survey corps captain Mikasa",
            "imageUrl": "https://example.com/mikasa.jpg",
        },
        {
            "id": "2",
            "title": "Flooding in Kathmandu valley Nepal",
            "snippet": "Heavy rainfall causes flood incident across Nepal capital",
            "imageUrl": "https://example.com/nepal_flood.jpg",
        },
    ]

    accepted, rejected = verify_image_results(candidates, spec)
    accepted_ids = [item["id"] for item in accepted]
    rejected_ids = [item["id"] for item in rejected]

    assert "2" in accepted_ids
    assert "1" in rejected_ids


def test_full_flow_nepal_after_mikasa_end_to_end(client):
    """End-to-end conversation flow:
    Turn 1: Tell me about Mikasa Ackerman
    Turn 2: Fetch some images -> Mikasa images
    Turn 3: Now fetch Nepal current incident images -> Must be Nepal images, NOT Mikasa!
    """
    owner = client.get("/v1/workspace/identity", headers={"X-HINAA-Dev-User": "alice"}).json()["userId"]
    service: ConversationService = client.app.state.service
    session_id = "test-nepal-mikasa-precedence"

    # Turn 1: Mikasa inquiry
    turn1 = asyncio.run(service.create_plan(
        TurnRequest(
            sessionId=session_id,
            conversationId=session_id,
            text="Tell me about Mikasa Ackerman",
            providerMode="mock",
        ),
        user_id=owner,
    ))

    # Turn 2: Referential image request
    turn2 = asyncio.run(service.create_plan(
        TurnRequest(
            sessionId=session_id,
            conversationId=session_id,
            text="Fetch some images",
            providerMode="mock",
        ),
        user_id=owner,
    ))
    tool_req2 = next((t for t in turn2.value.toolRequests if t.toolName == "image_search"), None)
    assert tool_req2 is not None
    assert tool_req2.parameters["canonicalSubject"] == "Mikasa Ackerman"

    # Turn 3: Explicit new topic - Nepal current incident images
    turn3 = asyncio.run(service.create_plan(
        TurnRequest(
            sessionId=session_id,
            conversationId=session_id,
            text="Now fetch Nepal current incident images",
            providerMode="mock",
        ),
        user_id=owner,
    ))
    tool_req3 = next((t for t in turn3.value.toolRequests if t.toolName == "image_search"), None)
    assert tool_req3 is not None
    subject = tool_req3.parameters["canonicalSubject"].lower()
    query = tool_req3.parameters["query"].lower()

    assert "mikasa" not in subject
    assert "ackerman" not in subject
    assert "mikasa" not in query
    assert "attack on titan" not in query
    assert "nepal" in subject
    assert "nepal" in query
