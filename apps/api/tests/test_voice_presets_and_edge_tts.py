"""Tests for cute girl Edge Neural TTS, Deepgram Aura presets, HeyGen status, and Live Call WS."""

from __future__ import annotations

from fastapi.testclient import TestClient

from hinaa_api.audio import ensure_wav_or_mp3
from hinaa_api.config import Settings
from hinaa_api.providers.deepgram_voice import DeepgramTTSProvider
from hinaa_api.providers.edge_tts_provider import EdgeNeuralTTSProvider, pick_edge_voice
from hinaa_api.providers.elevenlabs import ElevenLabsStatus
from hinaa_api.services import ProviderRouter
from hinaa_api.voice_fallback import clear_voice_cooldown, note_voice_failure


class _ElevenLabsRefusal(Exception):
    def __init__(self, status: ElevenLabsStatus) -> None:
        super().__init__(status.value)
        self.el_status = status


def test_edge_voice_selection_picks_cute_female_and_nepali() -> None:
    assert pick_edge_voice("Hi babe, ready to build?") == "en-US-AnaNeural"
    assert pick_edge_voice("मलाई तिमी कस्तो लाग्छ?") == "ne-NP-HemkalaNeural"
    assert pick_edge_voice("नमस्ते दोस्त!") == "hi-IN-SwaraNeural"
    assert pick_edge_voice("Hello", requested_voice="en-US-JennyNeural") == "en-US-JennyNeural"


def test_mp3_mpeg2_sync_header_is_preserved_not_wrapped_as_wav() -> None:
    fake_mp3 = b"\xff\xf3\x84\xc4" + b"\x00" * 128
    out_bytes, mime = ensure_wav_or_mp3(fake_mp3)
    assert mime == "audio/mpeg"
    assert out_bytes == fake_mp3


def test_provider_router_routes_edge_and_thalia_cleanly() -> None:
    settings = Settings(
        deepgram_api_key="dg-test-key",
        elevenlabs_api_key="el-test-key",
        elevenlabs_voice_id="voice-test",
    )
    router = ProviderRouter(settings)
    try:
        edge = router.tts("auto", "hinaa", "ana")
        assert isinstance(edge, EdgeNeuralTTSProvider)

        thalia = router.tts("auto", "hinaa", "thalia")
        assert isinstance(thalia, DeepgramTTSProvider)

        # Simulate ElevenLabs invoice cooldown and confirm auto skips straight to Deepgram
        note_voice_failure("elevenlabs", _ElevenLabsRefusal(ElevenLabsStatus.quotaFailed))
        cooled = router.tts("auto", "hinaa", None)
        assert isinstance(cooled, DeepgramTTSProvider)
    finally:
        clear_voice_cooldown("elevenlabs")


def test_voice_presets_endpoint_and_live_ws_text_turn() -> None:
    from hinaa_api.main import create_app

    app = create_app(Settings(provider_mode="mock"))
    with TestClient(app) as client:
        res = client.get("/v1/voice/presets")
        assert res.status_code == 200
        body = res.json()
        preset_ids = [item["id"] for item in body["presets"]]
        assert "edge:en-US-AnaNeural" in preset_ids
        assert "deepgram:aura-2-thalia-en" in preset_ids

        with client.websocket_connect("/ws/live") as ws:
            init_msg = ws.receive_json()
            assert init_msg["type"] == "state"
            ws.send_json({"type": "config", "voiceEngine": "browser"})
            cfg_ack = ws.receive_json()
            assert cfg_ack == {"type": "config.ack", "voiceEngine": "browser"}
            ws.send_json({"type": "text", "text": "Hello Hina!"})
            seen_types: list[str] = []
            for _ in range(8):
                frame = ws.receive()
                if "text" in frame and frame["text"]:
                    import json

                    evt = json.loads(frame["text"])
                    seen_types.append(str(evt.get("type")))
                    if evt.get("type") == "latency":
                        break
            assert "assistant.spoken" in seen_types
            assert "latency" in seen_types
