"""Conversation evaluation suite for Hina (Phase 2).

Each scenario is a real failure from the user's transcript with Hina, or a
positive case that must keep working. The suite runs the same checks the
chat path runs — sanction, gate, whitelist, memory, reply guard — so a
regression in any layer shows up here before it reaches the user.

Scenarios (from the 2026-11-13 transcript):
1. A complaint/question about hallucinations must NOT become a computer action.
2. "Talk in English" must stick.
3. "MP4, not NP4" must be remembered, and NP4/MMP4 must never ship.
4. A cinematic-video request must not produce a fake MP4.
5. "Stop" must report honestly how many jobs were actually cancelled.
6. GitHub: Hina must be able to list repos and switch the active set in
   conversation, instead of only working on one pre-selected repo.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from hinaa_api.config import Settings
from hinaa_api.memory.session_memory import SessionMemory
from hinaa_api.models import ToolRequest
from hinaa_api.reply_guard import check_reply
from hinaa_api.tools.intent_gate import gate_tool_requests, sanction_tools

COMPLAINT = "why whenever the model switches you hallucinate and do random things"
COMPLAINT_2 = "are you dumb? why did you switch to codestral and ignore my question"


def test_complaint_about_hallucinations_sanctions_no_computer_action() -> None:
    for text in (COMPLAINT, COMPLAINT_2, "why are you hallucinating and doing random things?"):
        sanction = sanction_tools(text)
        assert "computer_operator" not in sanction.allowed, text
        assert "terminal_hands" not in sanction.allowed, text
        assert not sanction.abort


def test_gate_drops_a_model_invented_computer_operator_on_a_complaint() -> None:
    invented = ToolRequest(
        toolName="computer_operator",
        parameters={"action": "open_application", "target": "something"},
    )
    kept, dropped, _sanction = gate_tool_requests(COMPLAINT, [invented])
    assert kept == []
    assert "computer_operator" in dropped


def test_a_real_os_request_still_works() -> None:
    sanction = sanction_tools("open chrome on my pc")
    assert "computer_operator" in sanction.allowed
    assert sanction.parameters["computer_operator"]["action"] == "open_application"


def test_mentioning_a_video_is_not_an_os_action() -> None:
    # The old MEDIA_PATTERN put computer_operator in allowed_tools for any
    # mention of "video"/"youtube"/"music" — including questions about them.
    sanction = sanction_tools("why did the video you promised never arrive?")
    assert "computer_operator" not in sanction.allowed


def test_stop_is_an_abort_not_a_tool_call() -> None:
    for text in ("stop", "cancel everything", "stop generating"):
        sanction = sanction_tools(text)
        assert sanction.abort, text
        assert not sanction.allowed, text


def _service():
    from hinaa_api.services import ConversationService

    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        GEMINI_API_KEY="",
        _env_file=None,
    )
    return ConversationService(settings)


def test_turn_whitelist_has_no_computer_action_for_a_complaint() -> None:
    from hinaa_intent_gate import Intent

    service = _service()
    allowed = service._turn_tool_whitelist(COMPLAINT, Intent.CHAT, history=[])
    assert "computer_operator" not in allowed
    assert "terminal_hands" not in allowed


def test_turn_whitelist_allows_os_action_when_asked() -> None:
    from hinaa_intent_gate import Intent

    service = _service()
    allowed = service._turn_tool_whitelist("open chrome on my pc", Intent.CHAT, history=[])
    assert "computer_operator" in allowed


def test_language_preference_is_remembered() -> None:
    mem = SessionMemory(session_limit=10, turn_limit=10)
    mem.learn_from_message("s1", "Talk in English")
    mem.learn_from_message("s1", "I said, Talk in English")
    facts = mem.learned_memories("s1")
    assert any("English" in f for f in facts)


def test_correction_is_remembered_and_invented_format_is_repaired() -> None:
    mem = SessionMemory(session_limit=10, turn_limit=10)
    mem.learn_from_message("s1", "I am talking about MP4, not NP4")
    assert any("MP4" in f and "NP4" in f for f in mem.learned_memories("s1"))
    out = check_reply("Here is your NP4 file, and the MMP4 version too.")
    assert "NP4" not in out.text and "MMP4" not in out.text
    assert "MP4" in out.text
    assert any(i.kind == "invented_format" for i in out.issues)


def test_video_generation_is_blocked_not_faked() -> None:
    from hinaa_api.creative.providers.video_generative_provider import (
        generative_video_provider,
    )

    with pytest.raises(RuntimeError):
        asyncio.run(generative_video_provider.execute_job({}))


def test_fake_veo_adapter_fails_honestly() -> None:
    from hinaa_api.media.timeline_spec import VertexVeoAdapter

    adapter = VertexVeoAdapter()
    job_id = asyncio.run(adapter.submit({"durationSeconds": 8}))
    with pytest.raises(Exception):
        asyncio.run(adapter.fetch(job_id))


def test_cancel_text_is_honest_about_the_count() -> None:
    # The old code always said "I have cancelled any running jobs", even
    # when zero jobs were running or it could not even look. The count now
    # decides the sentence; guard the source so it cannot silently regress.
    source = Path(__file__).resolve().parents[1].joinpath(
        "hinaa_api", "services.py"
    ).read_text(encoding="utf-8")
    assert '"Stopped. I have cancelled any running jobs."' not in source
    assert '"Stopped. No jobs were running."' in source
    assert "couldn't check whether any jobs were running" in source


def test_no_invented_computer_action_in_services() -> None:
    # The deterministic guarantee used to default to
    # {"action": "create_folder", "target": <the user's whole message>}.
    # That default must never come back.
    source = Path(__file__).resolve().parents[1].joinpath(
        "hinaa_api", "services.py"
    ).read_text(encoding="utf-8")
    assert '"action": "create_folder", "target": request.text' not in source


def test_github_list_and_switch_repos_in_conversation(monkeypatch, tmp_path) -> None:
    """Hina can list the token's repos and switch her active set."""
    import hinaa_api.integrations_hub.github_repos as repos_mod
    from hinaa_api.integrations_hub.github_repos import list_repos, set_active_repos

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/user/repos"
        return httpx.Response(
            200,
            json=[
                {
                    "full_name": "unesh123/hinamygirll",
                    "private": False,
                    "description": "Hina",
                    "default_branch": "main",
                    "language": "Python",
                    "pushed_at": "2026-11-11T20:32:58Z",
                    "archived": False,
                    "html_url": "https://github.com/unesh123/hinamygirll",
                },
                {
                    "full_name": "unesh123/other-repo",
                    "private": True,
                    "description": "",
                    "default_branch": "main",
                    "language": "TypeScript",
                    "pushed_at": "2026-11-01T00:00:00Z",
                    "archived": False,
                    "html_url": "https://github.com/unesh123/other-repo",
                },
            ],
        )

    monkeypatch.setattr(repos_mod, "transport", httpx.MockTransport(_handler))
    monkeypatch.setattr(repos_mod, "_token", lambda: "fake-token-for-test")
    monkeypatch.setattr(
        repos_mod, "_state_path", lambda: tmp_path / "github_active_repos.json"
    )
    found = asyncio.run(list_repos())
    assert [r["fullName"] for r in found] == [
        "unesh123/hinamygirll",
        "unesh123/other-repo",
    ]
    # Switch active set, then read it back — the same round-trip the
    # github_set_active_repos tool performs.
    active = set_active_repos(["unesh123/other-repo"])
    assert active == ["unesh123/other-repo"]
    assert json.loads((tmp_path / "github_active_repos.json").read_text())["repos"] == [
        "unesh123/other-repo"
    ]
    with pytest.raises(Exception):
        set_active_repos(["not-a-repo"])
