from __future__ import annotations

import pytest
from pydantic import ValidationError

from hinaa_api.config import Settings
from hinaa_api.realtime import segment_phrases
from hinaa_api.services import ProviderRouter
from hinaa_api.voice_performance import (
    ALLOWED_SSML_TAGS,
    VoicePerformancePlan,
    build_bounded_ssml,
    plan_voice_performance,
    speech_text_for_tts,
)


def test_all_voice_modes_are_bounded() -> None:
    cases = [
        ("hi hello namaste", "warm reply", "conversational", "bright"),
        ("debug this TypeError in FastAPI", "check the stack", "procedural", "professional"),
        ("this is a serious problem", "I can help calmly", "supportive", "calm"),
        ("great thanks it passed", "awesome", "conversational", "celebratory"),
        ("please consider carefully", "thinking about tradeoffs", "thoughtful", "thoughtful"),
        ("sorry for the error", "I am sorry", "supportive", "apologetic"),
        ("how was your day", "it was fine", "conversational", "warm"),
    ]
    for user, reply, depth, mode in cases:
        plan = plan_voice_performance(user_text=user, reply_text=reply, depth=depth)
        assert plan.mode == mode, (user, plan.mode, mode)
        assert 0.85 <= plan.pace <= 1.15
        assert -2.0 <= plan.pitch_semitones <= 2.0
        assert 0.75 <= plan.volume <= 1.0


def test_invalid_voice_plan_rejected() -> None:
    with pytest.raises(ValidationError):
        VoicePerformancePlan(pace=2.0)


def test_speech_only_pronunciation_does_not_mutate_display_intent() -> None:
    display = "Hinaa uses FastAPI and WebSocket with Gemini."
    spoken = speech_text_for_tts(display)
    assert "Hee-nah" in spoken
    assert "fast A P I" in spoken
    assert "Hinaa" in display  # display string unchanged by caller ownership


def test_ssml_allowlist_and_escaping() -> None:
    plan = VoicePerformancePlan(mode="warm", pace=1.0, pitch_semitones=0.5, volume=0.9)
    ssml = build_bounded_ssml('Say <script> & "hi"', plan)
    assert "<script>" not in ssml
    assert "&lt;script&gt;" in ssml
    assert "prosody" in ALLOWED_SSML_TAGS
    assert "audio" not in ALLOWED_SSML_TAGS


def test_segment_phrases_preserves_technical_tokens() -> None:
    text = (
        "Open https://example.com/docs and set HINAA_DATABASE_URL. "
        "File apps/web/src/App.tsx uses 3.14 as timeout."
    )
    chunks = segment_phrases(text, limit=90)
    joined = " ".join(chunks)
    assert "https://example.com/docs" in joined
    assert "HINAA_DATABASE_URL" in joined
    assert "App.tsx" in joined


def test_real_mode_router_never_returns_mock_llm() -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="test-key-not-used",
        AZURE_SPEECH_REGION="eastus",
        GEMINI_API_KEY="test-key-not-used",
        _env_file=None,
    )
    router = ProviderRouter(settings)
    mock = router.llm("mock")
    assert mock.id.startswith("mock")
    real = router.llm("real")
    assert not real.id.startswith("mock")
