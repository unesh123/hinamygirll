"""Tests for Module 02: Persistent Character Identity & Anti-Repetition."""

import pytest
from pathlib import Path
from hinaa_api.identity.models import CharacterIdentity, RelationshipMode, PersonaTraits
from hinaa_api.identity.anti_repetition import RepetitionDetector
from hinaa_api.identity.store import IdentityStore
from hinaa_api.identity.manager import IdentityManager


def test_character_identity_defaults():
    identity = CharacterIdentity()
    assert identity.name == "Hina"
    assert identity.active_mode == RelationshipMode.CO_PILOT
    assert identity.traits.intellect >= 0.9
    assert len(identity.invariants) >= 5


def test_anti_repetition_sanitizes_sentimental_loops():
    detector = RepetitionDetector()

    # Repetitive sentimental loop opening
    raw_response = (
        "Darling, you know you mean the world to me! "
        "Here is the architecture breakdown for BlueStacks 5 ADB integration:\n"
        "1. Check HD-Player.exe process.\n"
        "2. Connect via 127.0.0.1:5555."
    )
    cleaned, modified = detector.sanitize(raw_response)
    assert modified is True
    # The sentimental boilerplate is stripped
    assert not cleaned.startswith("Darling")
    assert "Here is the architecture breakdown" in cleaned


def test_anti_repetition_sanitizes_ai_boilerplate():
    detector = RepetitionDetector()

    raw_response = (
        "As an AI language model, I do not have personal opinions, but "
        "Isekai refers to a genre where a character is transported or reincarnated into another world."
    )
    cleaned, modified = detector.sanitize(raw_response)
    assert modified is True
    assert not cleaned.startswith("As an AI")
    assert "Isekai refers to" in cleaned


def test_anti_repetition_preserves_clean_responses():
    detector = RepetitionDetector()
    clean_text = "The ADB server is listening on port 5037 and the BlueStacks emulator is active."
    cleaned, modified = detector.sanitize(clean_text)
    assert modified is False
    assert cleaned == clean_text


def test_identity_store_roundtrip(tmp_path: Path):
    store_file = tmp_path / "test_identity.json"
    store = IdentityStore(file_path=store_file)

    identity = CharacterIdentity(
        name="Hina",
        active_mode=RelationshipMode.ANALYST,
        total_interactions=42,
    )
    assert store.save(identity) is True
    assert store_file.exists()

    loaded = store.load()
    assert loaded.name == "Hina"
    assert loaded.active_mode == RelationshipMode.ANALYST
    assert loaded.total_interactions == 42


def test_identity_manager_prompt_generation(tmp_path: Path):
    store_file = tmp_path / "test_mgr_identity.json"
    manager = IdentityManager(store=IdentityStore(file_path=store_file))

    manager.set_relationship_mode(RelationshipMode.AUTONOMOUS_OPERATOR)
    manager.update_traits(assertiveness=0.88, technical_depth=0.95)

    prompt_segment = manager.get_system_prompt_segment()
    assert "CHARACTER IDENTITY: HINA" in prompt_segment
    assert "OPERATOR" in prompt_segment
    assert "Never claim an action was done without verified tool execution" in prompt_segment

    count = manager.increment_interaction()
    assert count == 1
