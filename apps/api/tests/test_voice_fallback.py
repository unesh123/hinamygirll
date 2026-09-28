"""Fallback policy for her voice.

Her voice is an identity, so the primary is never skipped — but a vendor that
says "no credits" must not mean silence. These tests pin which failures another
vendor can cure, which voice speaks when we fall back, and that a hard refusal is
remembered briefly so the next turn goes straight to that voice.
"""
from __future__ import annotations

import pytest

from hinaa_api.providers.elevenlabs import ElevenLabsStatus
from hinaa_api.voice_fallback import (
    DEFAULT_HINAA_FALLBACK_VOICE,
    clear_voice_cooldown,
    fallback_voice_id,
    is_fallback_worthy,
    note_voice_failure,
    status_of,
    voice_on_cooldown,
)


class _ElevenLabsFailure(Exception):
    def __init__(self, status: ElevenLabsStatus) -> None:
        super().__init__(status.value)
        self.el_status = status


@pytest.fixture(autouse=True)
def _clean_cooldowns() -> None:
    clear_voice_cooldown()
    yield
    clear_voice_cooldown()


def test_fallback_voice_selection_is_per_companion() -> None:
    assert fallback_voice_id("hinaa", hinaa_voice="aura-2-thalia-en", hiro_voice="aura-2-odysseus-en") == "aura-2-thalia-en"
    assert fallback_voice_id("hiro", hinaa_voice="aura-2-thalia-en", hiro_voice="aura-2-odysseus-en") == "aura-2-odysseus-en"


def test_default_fallback_voice_is_a_female_aura_voice() -> None:
    assert DEFAULT_HINAA_FALLBACK_VOICE.startswith("aura")
    assert DEFAULT_HINAA_FALLBACK_VOICE.endswith("-en")


def test_quota_and_auth_failures_are_fallback_worthy() -> None:
    assert is_fallback_worthy(_ElevenLabsFailure(ElevenLabsStatus.quotaFailed))
    assert is_fallback_worthy(_ElevenLabsFailure(ElevenLabsStatus.authenticationFailed))
    assert is_fallback_worthy(_ElevenLabsFailure(ElevenLabsStatus.unavailable))
    assert is_fallback_worthy(_ElevenLabsFailure(ElevenLabsStatus.timeout))


def test_parameter_rejections_are_not_fallback_worthy() -> None:
    # A model/voice the vendor refuses would be refused by the next vendor too.
    assert not is_fallback_worthy(_ElevenLabsFailure(ElevenLabsStatus.modelUnsupported))
    assert not is_fallback_worthy(_ElevenLabsFailure(ElevenLabsStatus.voiceUnsupported))


def test_unknown_errors_are_fallback_worthy() -> None:
    assert is_fallback_worthy(RuntimeError("socket closed"))
    assert status_of(RuntimeError("socket closed")) is None


def test_hard_refusal_starts_a_cooldown() -> None:
    assert voice_on_cooldown("elevenlabs", now=1000.0) is False
    note_voice_failure("elevenlabs", _ElevenLabsFailure(ElevenLabsStatus.quotaFailed), now=1000.0)
    assert voice_on_cooldown("elevenlabs", now=1000.0) is True
    assert voice_on_cooldown("elevenlabs", now=1000.0 + 599.0) is True
    assert voice_on_cooldown("elevenlabs", now=1000.0 + 601.0) is False


def test_raw_transport_error_does_not_start_a_cooldown() -> None:
    note_voice_failure("elevenlabs", RuntimeError("connection reset"), now=1000.0)
    assert voice_on_cooldown("elevenlabs", now=1000.0) is False


def test_clear_voice_cooldown_forgets_one_provider() -> None:
    note_voice_failure("elevenlabs", _ElevenLabsFailure(ElevenLabsStatus.quotaFailed), now=1000.0)
    clear_voice_cooldown("elevenlabs")
    assert voice_on_cooldown("elevenlabs", now=1000.0) is False
