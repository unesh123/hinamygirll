"""
test_elevenlabs_unit.py

Offline unit tests for ElevenLabs STT, TTS, VoicePerformancePlanner, Alignment, and Key Isolation.
None of these tests make external API calls.
"""
import pytest
from hinaa_api.config import Settings
from hinaa_api.providers.elevenlabs import (
    ElevenLabsConfig,
    ElevenLabsError,
    ElevenLabsHTTPStreamingProvider,
    ElevenLabsSTTProvider,
    ElevenLabsStatus,
    VoicePerformancePlanner,
    ElevenLabsAlignmentSource,
    VisemeApproximationAdapter,
    ALLOWED_SEMANTIC_MODES,
    ELEVENLABS_SPEED_MAX,
    ELEVENLABS_SPEED_MIN,
    clamp_elevenlabs_speed,
    language_code_for_text,
    language_code_for_model,
    reason_from_body,
)
from hinaa_api.voice_profiles import CALIBRATIONS

def test_language_hint_is_text_aware_without_forcing_hindi() -> None:
    assert language_code_for_text("Explain the deployment plan clearly.") == "en"
    assert language_code_for_text("हिना, मुझे setup समझाओ।") == "hi"
    assert language_code_for_text("हिना, मलाई ComfyUI को setup बुझाऊ।") == "ne"


def test_stt_transcript_filtering():
    stt = ElevenLabsSTTProvider(ElevenLabsConfig())
    # Empty transcript
    assert stt.filter_transcript("") is None
    assert stt.filter_transcript("   ") is None

    # Devanagari & mixed-language text
    dev = "नमस्ते! HINAA कस्तो छौ?"
    assert stt.filter_transcript(dev) == dev

    # Final transcript duplication
    final_text = "Mero naam Hinaa ho."
    assert stt.filter_transcript(final_text, is_final=True) == final_text
    # Duplicate final suppressed
    assert stt.filter_transcript(final_text, is_final=True) is None

def test_voice_performance_planner_bounds():
    planner = VoicePerformancePlanner()
    for mode in ALLOWED_SEMANTIC_MODES:
        plan = planner.plan_delivery(mode)
        assert plan["deliveryMode"] == mode
        assert 0.0 <= plan["stability"] <= 1.0
        assert 0.0 <= plan["similarity"] <= 1.0
        assert 0.0 <= plan["style_intensity"] <= 1.0
        assert 0.5 <= plan["pace"] <= 2.0

    # Unrecognized mode defaults to neutral
    plan = planner.plan_delivery("arbitrary_invalid_mode")
    assert plan["deliveryMode"] == "neutral"

def test_warm_mode_is_persona_warm() -> None:
    """Warm mode must carry real emotional warmth, and Hinaa warmer than Hiro."""
    planner = VoicePerformancePlanner()
    hinaa = planner.plan_delivery("warm", "hinaa")
    hiro = planner.plan_delivery("warm", "hiro")

    # The warm mode is noticeably expressive: low stability (emotional range)
    # and a real style/warmth contribution, not the old flat defaults.
    assert hinaa["stability"] <= 0.42
    assert hinaa["style_intensity"] >= 0.30
    assert hinaa["pace"] <= 0.95  # slightly slower = more tender
    assert hinaa["similarity"] >= 0.75  # voice identity stays consistent

    # Per-companion bias: Hinaa speaks warmer/softer than Hiro.
    assert hinaa["stability"] < hiro["stability"]
    assert hinaa["style_intensity"] > hiro["style_intensity"]

    # Every semantic mode stays in bounds for both companions.
    for mode in ALLOWED_SEMANTIC_MODES:
        for companion in ("hinaa", "hiro"):
            plan = planner.plan_delivery(mode, companion)
            assert 0.0 <= plan["stability"] <= 1.0
            assert 0.0 <= plan["similarity"] <= 1.0
            assert 0.0 <= plan["style_intensity"] <= 1.0
            assert 0.5 <= plan["pace"] <= 2.0


def test_alignment_and_viseme_mapping():
    source = ElevenLabsAlignmentSource()
    adapter = VisemeApproximationAdapter()

    characters = ["N", "a", "m", "a", "s", "t", "e"]
    starts = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    ends = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]

    events = source.normalize_alignment(characters, starts, ends)
    assert len(events) == 7
    assert events[0] == {"char": "N", "startMs": 0, "endMs": 100}

    assert adapter.map_char_to_viseme("a") == "open"
    assert adapter.map_char_to_viseme("o") == "rounded"
    assert adapter.map_char_to_viseme("e") == "wide"
    assert adapter.map_char_to_viseme("z") == "neutral"

@pytest.mark.asyncio
async def test_synthesize_full_retries_transient_429_burst():
    """A transient 429 quota burst must not drop a mid-reply sentence.

    synthesize_full retries with short backoff and returns the recovered audio;
    a sustained 429 still raises so the realtime layer can log and move on.
    """
    import asyncio
    from unittest.mock import AsyncMock

    config = ElevenLabsConfig(api_key="fake_key", voice_id="fake_voice", tts_retry_backoff_s=0.0)
    provider = ElevenLabsHTTPStreamingProvider(config)

    calls = {"count": 0}

    async def fake_synthesize(
        text, *, voice=None, delivery_mode="warm", companion_id="hinaa", rate=None
    ):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ElevenLabsError(ElevenLabsStatus.quotaFailed, "quota burst")
        yield b"audio-bytes"

    provider.synthesize = fake_synthesize  # type: ignore[method-assign]

    result = await provider.synthesize_full("Hello", companion_id="hinaa")
    assert calls["count"] == 2
    assert result.value == b"audio-bytes"
    assert result.provider == "elevenlabs"


@pytest.mark.asyncio
async def test_synthesize_full_hard_failure_skips_retry():
    """Non-429 hard failures (auth/voice/timeout) raise immediately, never retry."""
    config = ElevenLabsConfig(
        api_key="fake_key", voice_id="fake_voice", tts_retry_attempts=2, tts_retry_backoff_s=0.0
    )
    provider = ElevenLabsHTTPStreamingProvider(config)
    calls = {"count": 0}

    async def fake_synthesize(
        text, *, voice=None, delivery_mode="warm", companion_id="hinaa", rate=None
    ):
        calls["count"] += 1
        raise ElevenLabsError(ElevenLabsStatus.authenticationFailed, "bad key")
        yield b""  # pragma: no cover - never reached

    provider.synthesize = fake_synthesize  # type: ignore[method-assign]

    with pytest.raises(ElevenLabsError) as exc_info:
        await provider.synthesize_full("Hello", companion_id="hinaa")
    assert exc_info.value.el_status is ElevenLabsStatus.authenticationFailed
    assert calls["count"] == 1  # no retry on hard failure


@pytest.mark.asyncio
async def test_synthesize_full_gives_up_after_bounded_retries():
    """Sustained 429s exhaust the bounded retries and raise instead of hanging."""
    config = ElevenLabsConfig(
        api_key="fake_key", voice_id="fake_voice", tts_retry_attempts=2, tts_retry_backoff_s=0.0
    )
    provider = ElevenLabsHTTPStreamingProvider(config)
    calls = {"count": 0}

    async def fake_synthesize(
        text, *, voice=None, delivery_mode="warm", companion_id="hinaa", rate=None
    ):
        calls["count"] += 1
        raise ElevenLabsError(ElevenLabsStatus.quotaFailed, "quota exhausted")
        yield b""  # pragma: no cover - never reached

    provider.synthesize = fake_synthesize  # type: ignore[method-assign]

    with pytest.raises(ElevenLabsError) as exc_info:
        await provider.synthesize_full("Hello", companion_id="hinaa")
    assert exc_info.value.el_status is ElevenLabsStatus.quotaFailed
    # attempts + 1 initial call, never more
    assert calls["count"] == config.tts_retry_attempts + 1


@pytest.mark.asyncio
async def test_the_synthesis_gate_bounds_in_flight_requests_across_instances(
    monkeypatch,
):
    """A live turn fans out one synthesis per phrase; the account caps at five.

    ElevenLabs answers the sixth concurrent request with 429 and the realtime
    layer drops that sentence, so the ceiling has to hold even though
    ProviderRouter builds a new provider for every single call.
    """
    import asyncio
    import httpx

    state = {"live": 0, "peak": 0}

    class _Response:
        status_code = 200

        async def aiter_bytes(self, chunk_size):
            await asyncio.sleep(0.02)
            yield b"audio"
            state["live"] -= 1

    class _StreamCtx:
        async def __aenter__(self):
            return _Response()

        async def __aexit__(self, *_exc):
            return False

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        def stream(self, *args, **kwargs):
            state["live"] += 1
            state["peak"] = max(state["peak"], state["live"])
            return _StreamCtx()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    config = ElevenLabsConfig(api_key="k", voice_id="v", tts_max_concurrency=4)

    results = await asyncio.gather(
        *[
            ElevenLabsHTTPStreamingProvider(config).synthesize_full(f"Phrase {i}")
            for i in range(12)
        ]
    )

    assert state["peak"] <= 4
    assert [r.value for r in results] == [b"audio"] * 12


NEPALI_PHRASE = "मलाई कम्प्युटर सेटअप बुझाऊ, छिटो भन।"
TURBO = "eleven_turbo_v2_5"


def _record_stream(monkeypatch, sent, status_code=200, error_body=b"", queries=None):
    """Stand in for httpx so a synthesis request is recorded, not sent.

    The response keeps the three members the provider actually uses: status_code,
    aread() for the error body, and aiter_bytes() for the audio. `queries` records
    the URL parameters too, because that is where the vendor reads output_format.
    """
    import httpx

    class _Response:
        def __init__(self):
            self.status_code = status_code

        async def aread(self):
            return error_body

        async def aiter_bytes(self, chunk_size):
            yield b"audio"

    class _Stream:
        async def __aenter__(self):
            return _Response()

        async def __aexit__(self, *_exc):
            return False

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        def stream(self, method, url, headers=None, params=None, json=None):
            sent.append(json)
            if queries is not None:
                queries.append(params)
            return _Stream()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)


def test_a_language_code_the_model_rejects_is_never_sent() -> None:
    """Measured against this account: turbo v2.5 answers 400 unsupported_language
    for 'ne' while 'hi' and 'en' return audio. The hint is enforced, not suggested,
    so every Nepali phrase of a live turn lost its voice to a field we chose to send.
    """
    assert language_code_for_text(NEPALI_PHRASE) == "ne"  # what the classifier says
    assert language_code_for_model(NEPALI_PHRASE, TURBO) is None  # what gets sent
    assert language_code_for_model("Explain the deployment plan.", TURBO) == "en"
    assert language_code_for_model("हिना, मुझे setup समझाओ।", TURBO) == "hi"
    # Multilingual v2 rejects the field for any value, and an unmeasured model is
    # left to detect the language itself: omission costs enforcement, never audio.
    assert language_code_for_model(NEPALI_PHRASE, "eleven_multilingual_v2") is None
    assert language_code_for_model(NEPALI_PHRASE, "eleven_future_model") is None


@pytest.mark.asyncio
async def test_a_nepali_phrase_on_turbo_sends_no_language_code(monkeypatch):
    sent = []
    _record_stream(monkeypatch, sent)
    provider = ElevenLabsHTTPStreamingProvider(
        ElevenLabsConfig(api_key="k", voice_id="v", model_id=TURBO)
    )

    result = await provider.synthesize_full(NEPALI_PHRASE, companion_id="hinaa")

    assert result.value == b"audio"
    assert "language_code" not in sent[0]
    await provider.synthesize_full("Set it for four oclock.", companion_id="hinaa")
    assert sent[1]["language_code"] == "en"


@pytest.mark.asyncio
async def test_a_rejected_synthesis_carries_the_vendors_reason(monkeypatch):
    """The mapped status said only "unavailable" for a parameter the model refused.

    That named nothing that was wrong, so six silent phrases in one turn stayed
    unexplained in the log; the vendor's own words now ride on the error.
    """
    body = (
        b'{"detail":{"type":"validation_error","code":"invalid_parameters",'
        b'"message":"Model \'eleven_turbo_v2_5\' does not support language_code \'ne\'.",'
        b'"status":"unsupported_language","param":"language_code"}}'
    )
    sent = []
    _record_stream(monkeypatch, sent, status_code=400, error_body=body)
    provider = ElevenLabsHTTPStreamingProvider(
        ElevenLabsConfig(api_key="k", voice_id="v", model_id=TURBO)
    )

    with pytest.raises(ElevenLabsError) as exc_info:
        await provider.synthesize_full(NEPALI_PHRASE, companion_id="hinaa")

    message = str(exc_info.value)
    assert "unsupported_language" in message
    assert "does not support language_code" in message
    assert "unavailable" not in message
    assert len(sent) == 1  # a rejected parameter is not retried as if it were a burst


def test_the_vendor_reason_stays_bounded_and_single_line():
    assert reason_from_body(b"") == "no response body"
    assert reason_from_body(b'{"detail":"Too many requests"}') == "Too many requests"
    padded = reason_from_body(b'{"detail":{"message":"' + b"x" * 4000 + b'"}}')
    assert len(padded) <= 200 and "\n" not in padded
    assert reason_from_body(b"<html>500 upstream</html>") == "upstream returned no structured reason"


def test_key_isolation():
    config = ElevenLabsConfig(api_key="secret_test_key_12345", voice_id="TRnaQb7q41oL7sV0w6Bu")
    safe_dict = config.to_browser_safe_dict()
    assert "api_key" not in safe_dict
    assert safe_dict["voicePreview"] == "TRna***"

def test_no_hardcoded_fake_phrase_in_executable_code():
    """Regression test: verifies that fake hardcoded recognizer strings do NOT exist in provider source files."""
    from pathlib import Path
    providers_dir = Path(__file__).resolve().parents[1] / "hinaa_api" / "providers"
    for py_file in providers_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "Sanchai hunuhunchha?" not in content, f"Hardcoded fake phrase found in {py_file.name}"
        assert "ElevenLabsContinuousRecognizer" not in content, f"Fake recognizer class found in {py_file.name}"

@pytest.mark.asyncio
async def test_elevenlabs_batch_stt_provider_mocked():
    """Verifies that ElevenLabsSTTProvider constructs valid WAV and calls speech-to-text API endpoint."""
    from unittest.mock import AsyncMock, patch
    import io
    import wave

    config = ElevenLabsConfig(api_key="fake_key", voice_id="fake_voice", model_id="scribe_v2")
    provider = ElevenLabsSTTProvider(config)

    # 1 second of 16kHz mono PCM16 silence
    dummy_pcm = b"\x00\x00" * 16000

    from unittest.mock import MagicMock, AsyncMock, patch

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "Namaste Hinaa"}

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        result = await provider.transcribe(dummy_pcm)

        assert result.value == "Namaste Hinaa"
        assert result.provider == "elevenlabs-scribe-v2"

        # Verify POST arguments
        assert mock_post.called
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["headers"]["xi-api-key"] == "fake_key"
        assert call_kwargs["data"]["model_id"] == "scribe_v2"
        assert "file" in call_kwargs["files"]
        filename, audio_bytes, mime = call_kwargs["files"]["file"]
        assert filename == "audio.wav"
        assert mime == "audio/wav"

        # Validate generated WAV container header
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            assert wf.getnframes() == 16000


def _turbo_provider(monkeypatch, sent):
    """An ElevenLabs provider whose outgoing synthesis payloads are recorded."""
    _record_stream(monkeypatch, sent)
    return ElevenLabsHTTPStreamingProvider(
        ElevenLabsConfig(api_key="k", voice_id="v", model_id=TURBO)
    )


@pytest.mark.asyncio
async def test_the_rate_a_caller_asks_for_reaches_the_request(monkeypatch):
    """Measured defect: voice_settings.speed was pinned to 0.9 here, so the one
    number that decides how fast she speaks answered for nobody.
    """
    sent = []
    provider = _turbo_provider(monkeypatch, sent)

    await provider.synthesize_full(
        "Explain the deployment plan.", companion_id="hinaa", rate=1.12
    )

    assert sent[0]["voice_settings"]["speed"] == 1.12


@pytest.mark.asyncio
async def test_a_caller_that_names_no_pace_keeps_the_semantic_mode_pace(monkeypatch):
    sent = []
    provider = _turbo_provider(monkeypatch, sent)

    await provider.synthesize_full(
        "Take your time with this one.",
        companion_id="hinaa",
        delivery_mode="calm",
    )

    pace = VoicePerformancePlanner().plan_delivery("calm", "hinaa")["pace"]
    assert sent[0]["voice_settings"]["speed"] == clamp_elevenlabs_speed(pace)


@pytest.mark.asyncio
async def test_a_rate_the_vendor_would_reject_is_clamped_not_sent(monkeypatch):
    """1.25 is answered with HTTP 400 invalid_voice_settings on this account, and
    the planner is allowed to emit up to 2.0. An unclamped pace does not degrade
    to a slower voice; it costs the phrase its audio entirely.
    """
    sent = []
    provider = _turbo_provider(monkeypatch, sent)

    await provider.synthesize_full("Too fast.", companion_id="hinaa", rate=2.0)
    await provider.synthesize_full("Too slow.", companion_id="hinaa", rate=0.4)

    assert [payload["voice_settings"]["speed"] for payload in sent] == [
        ELEVENLABS_SPEED_MAX,
        ELEVENLABS_SPEED_MIN,
    ]
    assert clamp_elevenlabs_speed(1.07) == 1.07  # inside the band, untouched


def test_every_advertised_pace_is_one_the_provider_will_accept():
    """The live client hard-codes "natural" and offers no picker, so these numbers
    ARE her speaking pace. They used to sit at 0.94-1.07 while the provider pinned
    0.9, which is the measured gap behind "she is talking so slow, I can read it
    faster than that".
    """
    for name, tuning in CALIBRATIONS.items():
        assert ELEVENLABS_SPEED_MIN <= tuning.rate <= ELEVENLABS_SPEED_MAX, name
    assert CALIBRATIONS["natural"].rate > 1.1, "the default must be brisk"
    assert CALIBRATIONS["lively"].rate >= CALIBRATIONS["natural"].rate
    assert CALIBRATIONS["soft"].rate <= CALIBRATIONS["natural"].rate


@pytest.mark.asyncio
async def test_the_service_layer_forwards_the_rate_it_accepts(monkeypatch):
    """The rate was dropped in services, not in the provider: synthesize_text took
    the argument and never passed it on the ElevenLabs branch, so the calibration
    the realtime session resolved died one call before the wire.
    """
    from types import SimpleNamespace

    from hinaa_api.config import Settings
    from hinaa_api.services import ConversationService

    sent = []
    provider = _turbo_provider(monkeypatch, sent)
    service = ConversationService(Settings())
    service.router = SimpleNamespace(tts=lambda mode, companion_id: provider)

    await service.synthesize_text(
        "Explain the deployment plan.", "hinaa", "elevenlabs", rate=1.15
    )
    assert sent[0]["voice_settings"]["speed"] == 1.15

    # With no explicit rate, the calibration he is on decides, and it still speaks.
    await service.synthesize_text(
        "Explain it again.", "hinaa", "elevenlabs", calibration="lively"
    )
    assert sent[1]["voice_settings"]["speed"] == CALIBRATIONS["lively"].rate


@pytest.mark.asyncio
async def test_the_requested_audio_format_goes_where_the_vendor_reads_it(monkeypatch):
    """Measured: with output_format inside the JSON body this account answered
    every request as mp3_44100_128, byte for byte, whatever was configured -- and
    refused to explain itself. The label put on those bytes comes from the same
    setting, so a pcm configuration would have handed the browser mp3 wearing a
    pcm name. The parameter belongs in the query string.
    """
    sent: list[dict] = []
    queries: list[dict] = []
    _record_stream(monkeypatch, sent, queries=queries)
    provider = ElevenLabsHTTPStreamingProvider(
        ElevenLabsConfig(
            api_key="k", voice_id="v", model_id=TURBO, output_format="pcm_16000"
        )
    )

    await provider.synthesize_full("Give me raw samples.", companion_id="hinaa")

    assert queries[0] == {"output_format": "pcm_16000"}
    assert "output_format" not in sent[0]

