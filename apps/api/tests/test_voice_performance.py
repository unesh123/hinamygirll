from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from hinaa_api.config import Settings
from hinaa_api.models import SpeechRequest
from hinaa_api.providers.mock import MockTTSProvider
from hinaa_api.realtime import segment_phrases
from hinaa_api.services import ConversationService, ProviderRouter
from hinaa_api.voice_performance import (
    ALLOWED_SSML_TAGS,
    VoicePerformancePlan,
    build_bounded_ssml,
    plan_voice_performance,
    speech_text_for_tts,
    strip_greeting,
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


def test_spoken_channel_carries_no_decoration() -> None:
    cases = [
        ("Hey babe, how's your day going? 🔥", "Hey how's your day going?"),
        ("I set it for 4:00, babe. ✅ 3 reminders", "I set it for 4:00. 3 reminders"),
        ("Done BABES 🎉🫡 — cost $4.99 for 25 images", "Done — cost $4.99 for 25 images"),
        ("See you later, babe. Love you.", "See you later. Love you."),
        ("Babe, tell me more", "tell me more"),
    ]
    for display, expected in cases:
        assert speech_text_for_tts(display) == expected, display


def test_hindi_and_nepali_pet_names_leave_the_spoken_channel() -> None:
    # A measured Nepali voice turn opened with "ए बाबु," because the strip list
    # covered Latin spellings only. The vocative in front of the term goes with it.
    assert speech_text_for_tts("ए बाबु, कम्प्युटर सेटअपको कुरा गरौं।") == (
        "कम्प्युटर सेटअपको कुरा गरौं।"
    )
    assert speech_text_for_tts("नमस्ते जानू, यो हेर।") == "नमस्ते यो हेर।"
    # The next live turn opened with "अरे बाबे," -- the Latin term written the way
    # a Nepali reply spells it, which the -ु/-ू list did not cover.
    assert speech_text_for_tts("अरे बाबे, यो कम्प्युटरको setup हो।") == (
        "यो कम्प्युटरको setup हो।"
    )
    assert speech_text_for_tts("बेबी, यो हेर।") == "यो हेर।"
    # A name that merely contains the pet name keeps it, and जान ("life") is not
    # an address term here, so none of that content is cost.
    assert speech_text_for_tts("बाबुराज ko kaam") == "बाबुराज ko kaam"
    assert speech_text_for_tts("जान लेने जोखिम छ।") == "जान लेने जोखिम छ।"
    assert speech_text_for_tts("बाबा lekhchha") == "बाबा lekhchha"
    # The same term glued to a postposition is a possessive, not an address.
    assert speech_text_for_tts("बाबेको कम्प्युटर खराब छ।") == "बाबेको कम्प्युटर खराब छ।"


def test_the_greeting_she_is_told_to_use_leaves_the_text_channel() -> None:
    """Measured on a live turn: the first delta was "Arey babe, " and the plan
    opened the same way, so the surface showed the chat model greeting him even
    though the audio never said it.
    """
    assert strip_greeting("Arey babe, ") == ""
    assert strip_greeting("babe, tell me more") == "tell me more"
    assert strip_greeting("ए बाबु, कम्प्युटर सेटअप हेर।") == (
        "कम्प्युटर सेटअप हेर।"
    )
    # Nothing here is a greeting, so nothing here may go.
    assert strip_greeting("Babel is a compiler.") == "Babel is a compiler."
    assert strip_greeting("Here is your plan.") == "Here is your plan."
    assert strip_greeting("Arey, that was fast") == "Arey, that was fast"
    # A term the stream cut in half cannot be told from content. It stays on
    # screen exactly as she wrote it rather than being guessed at.
    assert strip_greeting("Arey ba") == "Arey ba"
    # The Roman interjection goes with the term in the audio too, which the
    # Devanagari-only vocative list used to leave behind.
    assert speech_text_for_tts("Arey babe, aaj ka plan simple hai.") == (
        "aaj ka plan simple hai."
    )
    # The next live turn opened the same way in Devanagari, with the Latin term
    # spelled the way Hindi says it, and the greeting went out in both channels.
    assert strip_greeting("अरे बेब, आज रात की ट्रेनिंग सेशन है।") == (
        "आज रात की ट्रेनिंग सेशन है।"
    )
    assert speech_text_for_tts("अरे बेब, तैयारी शुरू करो।") == "तैयारी शुरू करो।"
    assert speech_text_for_tts("बेबसाइट खोलो।") == "बेबसाइट खोलो।"
    # The next live turn opened with a salutation in front of the term and an
    # exclamation behind it, which an anchored, comma-only rule matched nothing.
    assert strip_greeting("नमस्ते बेब! आज शाम के ट्रेनिंग सेशन के लिए तैयार हो जाओ।") == (
        "आज शाम के ट्रेनिंग सेशन के लिए तैयार हो जाओ।"
    )
    assert strip_greeting("I set it at six, babe. ✅") == "I set it at six. ✅"


def test_the_greeting_strip_rewrites_nothing_but_the_greeting() -> None:
    """The strip runs on every delta of a streamed turn, so a rule that tidies as
    it goes would reflow his whole reply: paragraph breaks and table rows are what
    he reads on screen, and a word that happens to open like a pet name is content.
    """
    reply = "Arey babe, here is the plan.\n\n| # | Item |\n|---:|---|\n| 1 | oats |\n"
    assert strip_greeting(reply) == "here is the plan.\n\n| # | Item |\n|---:|---|\n| 1 | oats |\n"
    assert strip_greeting("\n\nArey babe, today we train.") == "\n\ntoday we train."
    assert strip_greeting("Use the baby monitor in the nursery.\n") == (
        "Use the baby monitor in the nursery.\n"
    )
    # A term set off by a comma at the end of a clause is the address, so it goes
    # with the comma that introduced it.
    assert strip_greeting("see you later, babe, ok") == "see you later, ok"
    # The fourth live turn opened with a salutation that is not a pet name, in a
    # delta of its own. मेरे is also the ordinary "my", so only the proven
    # address goes.
    assert strip_greeting("अरे मेरे ") == ""
    assert strip_greeting("अरे मेरे, आज रात की ट्रेनिंग सेशन है।") == (
        "आज रात की ट्रेनिंग सेशन है।"
    )
    assert strip_greeting("मेरे पास पानी की बोतल है।") == "मेरे पास पानी की बोतल है।"
    # The fifth live turn opened with a bare interjection in a chunk of its own.
    assert strip_greeting("अरे ") == ""
    assert strip_greeting("Arey!") == ""
    # A chunk that could be half a real word is content, not a greeting.
    assert strip_greeting("are ") == "are "


def test_a_voice_turn_never_reads_a_markdown_table_aloud() -> None:
    """Measured on a live turn: asked what to do before training, she answered with
    a Markdown table and the audio spoke ":---:---:" and the citation numbers too.
    177 words, 82 seconds, for one question he could read in fifteen.
    """
    display = (
        "Here is your plan.\n\n"
        "## Pre-Training Routine\n\n"
        "| Timing | Action |\n"
        "| :--- | :--- |\n"
        "| 1.5 - 2 Hours Before | Eat oats [2] |\n"
        "| 10 - 15 Minutes Before | Stretch [2, 4] |\n"
    )
    spoken = speech_text_for_tts(display)
    assert ":---" not in spoken
    assert "|" not in spoken
    assert "[2" not in spoken
    # Removing the structure must not cost a word of what it held.
    assert "1.5 - 2 Hours Before" in spoken
    assert "10 - 15 Minutes Before" in spoken
    assert "Eat oats" in spoken
    assert "Stretch" in spoken
    assert "Pre-Training Routine" in spoken


def test_decoration_removal_does_not_cost_content() -> None:
    # A TTS engine reads an emoji as a word, so it goes; everything the voice has
    # to report stays. "Babel" is not a pet name and Devanagari is not decoration.
    spoken = speech_text_for_tts("नमस्ते babe! ठीक है, कोई बात नहीं 🦊🌧️")
    assert spoken.startswith("नमस्ते ठीक है")
    assert "babe" not in spoken.lower()
    assert speech_text_for_tts("Babel is a compiler, not a pet name.") == (
        "Babel is a compiler, not a pet name."
    )
    assert speech_text_for_tts("That is fire🔥dude") == "That is fire dude"
    # Decoration alone has nothing to say, and an empty phrase must not be sent.
    assert speech_text_for_tts("🙂") == ""


def test_speaker_button_hands_the_provider_shaped_text() -> None:
    # The Talk page shapes inside the realtime pipeline; the chat page's speaker
    # button goes through SpeechRequest, which had no shaping at all. Audio bytes
    # cannot prove the difference (two identical requests came back at 33481 and
    # 29720), so the assertion is on the exact string the provider is handed.
    seen: list[str] = []

    class RecordingTTS(MockTTSProvider):
        async def synthesize(self, text: str, voice: str):  # type: ignore[override]
            seen.append(text)
            return await super().synthesize(text, voice)

    service = ConversationService(
        Settings(HINAA_PROVIDER_MODE="mock", _env_file=None)
    )
    service.router.mock_tts = RecordingTTS()

    reply = "I set it for 4:00, babe. ✅ 3 reminders 💜"
    asyncio.run(service.synthesize(SpeechRequest(text=reply, providerMode="mock")))
    assert seen == ["I set it for 4:00. 3 reminders"]

    # A reply that is nothing but decoration still has to produce audio rather
    # than an empty request, so the original text is what gets sent.
    seen.clear()
    asyncio.run(service.synthesize(SpeechRequest(text="🙂", providerMode="mock")))
    assert seen == ["🙂"]


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
