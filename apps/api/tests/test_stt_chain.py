"""Whether she can hear a microphone at all, tested on the bytes the socket carries.

/v1/realtime accumulates raw s16le PCM, and every real turn used to die in
transcription: the vendor was told the audio was webm when it was not, and the
model named only exists on Deepgram's realtime endpoint. These cases pin what
makes a voice turn survive -- a container that matches the bytes, a model the
endpoint accepts, the right vendor for the language he spoke in, and a dead
vendor that falls through instead of ending the session.
"""

from __future__ import annotations

import asyncio
import io
import struct
import wave

import httpx
import pytest

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.providers.base import ProviderResult
from hinaa_api.providers.deepgram_voice import DeepgramSTTProvider, pcm_to_wav
from hinaa_api.services import ConversationService, ProviderRouter


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "HINAA_PROVIDER_MODE": "mock",
        "HINAA_AUTH_MODE": "dev",
        "HINAA_PERSISTENCE_ENABLED": False,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _pcm(seconds: float = 0.25) -> bytes:
    frames = int(16_000 * seconds)
    return struct.pack(f"<{frames}h", *([1_000] * frames))


class _Recorder:
    """Stands in for httpx so the request shape is what is under test."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def install(self, monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
        recorder = self

        class _Response:
            status_code = 200
            content = b""

            def json(self) -> dict:
                return payload

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_exc):
                return False

            async def post(self, url, headers=None, params=None, content=None, timeout=None):
                recorder.calls.append(
                    {"url": url, "headers": headers, "params": params, "content": content}
                )
                return _Response()

        monkeypatch.setattr(httpx, "AsyncClient", _Client)


def test_deepgram_is_sent_a_wav_and_a_prerecorded_model(monkeypatch):
    recorder = _Recorder()
    recorder.install(
        monkeypatch,
        {"results": {"channels": [{"alternatives": [{"transcript": " call the bank "}]}]}},
    )
    provider = DeepgramSTTProvider("key", "https://api.deepgram.test", model="nova-2-general")

    result = asyncio.run(provider.transcribe(_pcm(), "en-US"))

    call = recorder.calls[0]
    assert call["headers"]["Content-Type"] == "audio/wav"
    assert call["params"]["model"] == "nova-2-general"
    assert call["content"][:4] == b"RIFF" and call["content"][8:12] == b"WAVE"
    assert result.value == "call the bank"
    assert result.latency_ms >= 0


def test_the_wav_wrapper_declares_the_sample_rate_the_socket_uses():
    with wave.open(io.BytesIO(pcm_to_wav(_pcm(seconds=1.0))), "rb") as handle:
        assert (handle.getframerate(), handle.getnchannels(), handle.getsampwidth()) == (
            16_000,
            1,
            2,
        )


def test_a_rejected_audio_raises_a_typed_error_not_a_bare_exception(monkeypatch):
    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def post(self, *a, **k):
            class _Response:
                status_code = 404
                text = '{"message":"model not found"}'

                def json(self):
                    return {"message": "model not found"}

            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    provider = DeepgramSTTProvider("key", "https://api.deepgram.test")

    with pytest.raises(HinaaError) as raised:
        asyncio.run(provider.transcribe(_pcm(), "en-US"))

    assert raised.value.code == "STT_PROVIDER_REJECTED"
    assert raised.value.developer_message == "model not found"


def test_english_voice_starts_on_deepgram_and_hindi_voice_on_scribe():
    settings = _settings(ELEVENLABS_API_KEY="el-test", DEEPGRAM_API_KEY="dg-test")
    assert settings.deepgram_configured and settings.elevenlabs_configured
    router = ProviderRouter(settings)

    english = [p.id for p in router.stt_candidates("real", "en-US")]
    hindi = [p.id for p in router.stt_candidates("real", "hi-IN")]

    assert english[0] == "deepgram"
    assert hindi[0].startswith("elevenlabs")
    # An English-only nova model on Hindi audio returns confident nonsense.
    assert "deepgram" not in hindi


def test_only_the_mock_and_local_paths_short_circuit_the_chain(monkeypatch):
    router = ProviderRouter(_settings())
    assert [p.id for p in router.stt_candidates("mock", "en-US")] == ["mock-stt-v1"]
    assert len(router.stt_candidates("local", "en-US")) == 1


class _Failing:
    id = "first-vendor"

    async def transcribe(self, pcm, language):
        raise HinaaError("STT_PROVIDER_REJECTED", "vendor is down", 502, True)


class _Silent:
    id = "silent-vendor"

    async def transcribe(self, pcm, language):
        return ProviderResult("   ", self.id, 12)


class _Working:
    id = "working-vendor"

    async def transcribe(self, pcm, language):
        return ProviderResult("remind me to call sile", self.id, 340)


@pytest.mark.parametrize(
    "vendors,expected",
    [
        ([_Failing(), _Working()], "remind me to call sile"),
        ([_Silent(), _Working()], "remind me to call sile"),
    ],
    ids=["vendor-rejected", "vendor-heard-nothing"],
)
def test_one_dead_vendor_does_not_end_a_voice_turn(vendors, expected):
    service = ConversationService(_settings())
    service.router.stt_candidates = lambda mode, language: list(vendors)

    result = asyncio.run(service.transcribe(_pcm(), "en-US", "real"))

    assert result.value == expected
    assert result.provider == "working-vendor"


def test_every_vendor_failing_reports_who_and_why_once():
    service = ConversationService(_settings())
    service.router.stt_candidates = lambda mode, language: [_Failing(), _Silent()]

    with pytest.raises(HinaaError) as raised:
        asyncio.run(service.transcribe(_pcm(), "en-US", "real"))

    assert raised.value.code == "STT_UNAVAILABLE"
    assert raised.value.retryable is True
    assert raised.value.developer_message == "first-vendor=STT_PROVIDER_REJECTED; silent-vendor=empty"


def test_a_voice_turn_with_no_configured_vendor_says_it_is_not_configured():
    service = ConversationService(_settings())

    with pytest.raises(HinaaError) as raised:
        asyncio.run(service.transcribe(b"", "en-US", "real"))

    # A missing vendor is a fact about the setup, not a bad luck that a retry
    # could clear, so the client gets the 503 that the settings page reports.
    assert raised.value.code == "LOCAL_STT_UNAVAILABLE"
    assert raised.value.status_code == 503
    assert raised.value.user_action_required is True


def test_an_unwired_vendor_is_not_blamed_on_the_vendor_behind_it():
    reached: list[str] = []

    class _Unwired:
        id = "unwired-vendor"

        async def transcribe(self, pcm, language):
            raise HinaaError("LOCAL_STT_UNAVAILABLE", "not configured", 503, False)

    class _Recording:
        id = "second-vendor"

        async def transcribe(self, pcm, language):
            reached.append(self.id)
            return ProviderResult("hello", self.id, 10)

    service = ConversationService(_settings())
    service.router.stt_candidates = lambda mode, language: [_Unwired(), _Recording()]

    with pytest.raises(HinaaError) as raised:
        asyncio.run(service.transcribe(_pcm(), "en-US", "real"))

    assert raised.value.code == "LOCAL_STT_UNAVAILABLE"
    assert reached == []
