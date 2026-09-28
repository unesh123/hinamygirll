"""Unit tests for Hina Astra Entity Brain."""

import pytest
from hinaa_api.astra.entities.models import EntityState
from hinaa_api.astra.entities.service import EntityBrainService


def test_entity_extraction_and_pronoun_resolution_lifecycle():
    service = EntityBrainService()
    convo_id = "test-convo-mikasa"

    # Turn 1: "Who is Mikasa Ackerman?"
    turn1_text = "Who is Mikasa Ackerman?"
    entities_turn1 = service.process_turn(convo_id, turn1_text, turn_number=1)
    assert len(entities_turn1) >= 1
    active_character = entities_turn1[0]
    assert active_character.canonical_name == "Mikasa Ackerman"
    assert active_character.domain == "Attack on Titan"
    assert active_character.attributes.get("gender") == "female"
    assert active_character.salience == 1.0

    # Turn 2: "tell me more about her"
    turn2_text = "tell me more about her"
    resolution2 = service.resolve_reference(convo_id, turn2_text)
    assert resolution2.has_reference is True
    assert resolution2.resolved_entity is not None
    assert resolution2.resolved_entity.canonical_name == "Mikasa Ackerman"
    assert "Mikasa Ackerman" in resolution2.canonical_query

    # Process turn 2 to update mentions/salience
    service.process_turn(convo_id, turn2_text, turn_number=2)

    # Turn 3: "show images"
    turn3_text = "show images"
    resolution3 = service.resolve_reference(convo_id, turn3_text)
    assert resolution3.has_reference is True
    assert resolution3.resolved_entity is not None
    assert resolution3.resolved_entity.canonical_name == "Mikasa Ackerman"
    # Grounded tool query must be pure subject + domain, zero noise words!
    assert resolution3.grounded_tool_query == "Mikasa Ackerman Attack on Titan"


def test_salience_decay():
    service = EntityBrainService()
    convo_id = "test-decay"

    # Turn 1 introduces Mikasa
    service.process_turn(convo_id, "Who is Mikasa Ackerman?", turn_number=1)
    e1 = service.get_active_entities(convo_id)[0]
    initial_salience = e1.salience
    assert initial_salience == 1.0

    # Turn 2, 3, 4 without mentioning Mikasa
    service.process_turn(convo_id, "Let's talk about Python programming", turn_number=2)
    service.process_turn(convo_id, "How do async queues work?", turn_number=3)
    service.process_turn(convo_id, "Tell me about Docker containers", turn_number=4)

    # Mikasa's salience must have decayed
    active = service.get_active_entities(convo_id, top_k=10)
    mikasa = next((e for e in active if e.canonical_name == "Mikasa Ackerman"), None)
    if mikasa:
        assert mikasa.salience < initial_salience


def test_file_entity_resolution():
    service = EntityBrainService()
    convo_id = "test-file"

    # Turn 1 mentions a file
    service.process_turn(convo_id, "Check the implementation in Hero.tsx", turn_number=1)
    active = service.get_active_entities(convo_id)
    assert any(e.canonical_name == "Hero.tsx" and e.entity_type == "file" for e in active)

    # Turn 2 refers to "that file"
    res = service.resolve_reference(convo_id, "Can you make that file shorter?")
    assert res.has_reference is True
    assert res.resolved_entity is not None
    assert res.resolved_entity.canonical_name == "Hero.tsx"
