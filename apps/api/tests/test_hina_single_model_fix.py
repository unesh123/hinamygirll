"""Regression tests for the "Hina got dumb mid-chat" fix (2026-11-13).

The transcript failures were:
- Qwen (qwen/qwen3.8-max:free) silently switching to Mistral / Cohere /
  Gemini / a canned local-rule engine, losing language and corrections.
- The XKiro allow-list ending in "*", so any model ID was accepted.
- No stored language preference or "X, not Y" correction.
- Invented video formats (NP4 / MMP4) shipping to the user.
- A fake Veo adapter returning a 24-byte "MP4" header as a success.
- A fabricated mock GitHub PR URL.
"""
from __future__ import annotations

import asyncio

import pytest

from hinaa_api.cognitive.resilient_router import ResilientProviderRouter, TaskProfile
from hinaa_api.config import Settings
from hinaa_api.memory.session_memory import SessionMemory
from hinaa_api.reply_guard import check_reply


def _settings() -> Settings:
    return Settings(_env_file=None, HINAA_PROVIDER_MODE="mock")


def test_auto_fallback_is_off_by_default() -> None:
    assert _settings().auto_fallback_enabled is False


def test_xkiro_allow_list_has_no_wildcard_and_is_qwen_only() -> None:
    settings = _settings()
    models = settings.xkiro_allowed_models
    assert "*" not in models
    assert models, "allow-list must not be empty"
    assert all(m.startswith("qwen/") for m in models), models


def test_resolve_xkiro_model_rejects_other_families() -> None:
    settings = _settings()
    assert settings.resolve_xkiro_model("qwen/qwen3.8-max:free") == "qwen/qwen3.8-max:free"
    for bad in (
        "mistralai/codestral-2508",
        "mistralai/ministral-14b",
        "cohere/command-a-reasoning",
        "gemini-3.5-flash",
        "deepseek/deepseek-v4.1-flash:free",
    ):
        with pytest.raises(ValueError):
            settings.resolve_xkiro_model(bad)


def test_resilient_router_never_silently_degrades_to_local_rule() -> None:
    router = ResilientProviderRouter()
    assert "local_rule" not in router.rank_providers(TaskProfile(complexity=0.9))
    assert "local_rule" not in router.select_healthy_provider_chain()
    # Explicitly asking for it is still allowed.
    assert "local_rule" in router.select_healthy_provider_chain(
        preferred_provider="local_rule"
    )


def test_session_memory_learns_language_preference() -> None:
    mem = SessionMemory(session_limit=10, turn_limit=10)
    mem.learn_from_message("s1", "Talk in English")
    assert any("English" in fact for fact in mem.learned_memories("s1"))


def test_session_memory_learns_correction() -> None:
    mem = SessionMemory(session_limit=10, turn_limit=10)
    mem.learn_from_message("s1", "I am talking about MP4, not NP4")
    assert any("MP4" in fact and "NP4" in fact for fact in mem.learned_memories("s1"))


def test_reply_guard_repairs_invented_video_formats() -> None:
    out = check_reply("Here is your NP4 file, and the MMP4 version too.")
    assert "NP4" not in out.text
    assert "MMP4" not in out.text
    assert "MP4" in out.text
    assert any(i.kind == "invented_format" for i in out.issues)


def test_fake_veo_adapter_fails_honestly() -> None:
    from hinaa_api.media.timeline_spec import VertexVeoAdapter

    adapter = VertexVeoAdapter()
    job_id = asyncio.run(adapter.submit({"durationSeconds": 8}))
    # poll() still reports the in-memory job, but fetch() must never hand
    # back a fake MP4 file as a success.
    with pytest.raises(Exception):
        asyncio.run(adapter.fetch(job_id))
