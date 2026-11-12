import pytest
from fastapi.testclient import TestClient

from hinaa_api.main import app
from hinaa_api.prompts.persona_modes import (
    get_persona_layer,
    build_persona_prime_prompt,
    get_persona_prime_quote,
    PRIME_COMMUNICATION_PRINCIPLES,
    DEFAULT_PERSONA_MODE,
)
from hinaa_api.identity.models import PersonaTraits, RelationshipMode
from hinaa_api.identity import get_identity_manager


def test_persona_prime_prompt_generation():
    prompt = get_persona_layer("prime")
    assert "HINA PERSONA PRIME" in prompt
    assert "Directness 90%" in prompt
    assert "Sarcasm 45%" in prompt
    assert "Technical Depth 95%" in prompt
    assert "Formality 20%" in prompt
    assert "10 INVARIANT COMMUNICATION PRINCIPLES" in prompt
    assert "Start directly with the answer" in prompt


def test_persona_unfiltered_direct_alias():
    prompt_alias = get_persona_layer("unfiltered_direct")
    assert "HINA PERSONA PRIME" in prompt_alias


def test_persona_prime_quote_calibration():
    quote_default = get_persona_prime_quote(0.9, 0.45, 0.95, 0.2)
    assert "Give me the actual problem" in quote_default

    quote_sarcastic = get_persona_prime_quote(0.9, 0.75, 0.95, 0.2)
    assert "stop guessing" in quote_sarcastic


def test_personality_profile_endpoints():
    client = TestClient(app)
    # Reset to default calibration first
    reset_res = client.put(
        "/api/personality/profile",
        json={"traits": {"directness": 0.90, "sarcasm": 0.45, "technical_depth": 0.95, "formality": 0.20}},
    )
    assert reset_res.status_code == 200

    res = client.get("/api/personality/profile")
    assert res.status_code == 200
    data = res.json()
    assert data["profile"] == "HINA PERSONA PRIME"
    assert data["defaultMode"] == "UNFILTERED_DIRECT"
    assert "traits" in data
    assert data["traits"]["directness"] == 0.90
    assert data["traits"]["sarcasm"] == 0.45
    assert len(data["communicationPrinciples"]) == 10

    # Test update
    update_res = client.put(
        "/api/personality/profile",
        json={"traits": {"directness": 0.95, "sarcasm": 0.50}},
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["traits"]["directness"] == 0.95
    assert updated_data["traits"]["sarcasm"] == 0.50


def test_large_string_no_8000_cap():
    from hinaa_api.main import ProjectTaskBody, CreateTaskBody, TurnRequest
    large_text = "A" * 25000
    task_body = ProjectTaskBody(title="Large task", detail=large_text)
    assert len(task_body.detail) == 25000

    create_task = CreateTaskBody(goal=large_text)
    assert len(create_task.goal) == 25000

    turn_req = TurnRequest(sessionId="sess-123", text=large_text)
    assert len(turn_req.text) == 25000


def test_exact_message_archive_record():
    from hinaa_api.persistence.orm import ExactMessageArchiveRecord
    rec = ExactMessageArchiveRecord(
        conversation_id="conv-123",
        message_id="msg-456",
        user_id="usr-789",
        role="user",
        raw_text="Hello Hina, exact byte verification.",
        char_count=35,
        byte_count=35,
        estimated_tokens=8,
        attachment_metadata="[]",
    )
    assert rec.role == "user"
    assert rec.byte_count == 35
    assert rec.char_count == 35
    assert rec.estimated_tokens == 8
