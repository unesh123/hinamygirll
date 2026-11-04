"""Pytest suite for Voice Turn Lifecycle State Machine & Barge-In Engine."""

import pytest
import time
from hinaa_api.voice.lifecycle import VoiceLifecycleManager, VoiceTurnState


def test_initial_lifecycle_state():
    mgr = VoiceLifecycleManager("test-session")
    assert mgr.state == VoiceTurnState.IDLE
    assert mgr.current_generation == 0
    assert mgr.active_turn is None
    assert len(mgr.history) == 0


def test_turn_progression_nominal():
    mgr = VoiceLifecycleManager("test-session")
    turn = mgr.start_listening(generation=1)
    assert mgr.state == VoiceTurnState.LISTENING
    assert mgr.current_generation == 1
    assert turn.turn_id.startswith("vturn-1-1")

    # Speech detected
    mgr.mark_speech_detected()
    assert mgr.state == VoiceTurnState.SPEECH_DETECTED
    assert turn.speech_detected_at is not None

    # STT Transcribing
    mgr.start_transcribing()
    assert mgr.state == VoiceTurnState.TRANSCRIBING
    assert turn.stt_started_at is not None

    # STT finished
    time.sleep(0.01)
    mgr.finish_transcribing("Hello Hinaa", "deepgram-nova-2")
    assert turn.transcript == "Hello Hinaa"
    assert turn.stt_provider == "deepgram-nova-2"
    assert turn.stt_latency_ms is not None
    assert turn.stt_latency_ms >= 5.0

    # Thinking
    mgr.start_thinking()
    assert mgr.state == VoiceTurnState.THINKING

    # First token
    time.sleep(0.01)
    mgr.mark_first_token()
    assert turn.first_token_at is not None
    assert turn.ttft_ms is not None
    assert turn.ttft_ms >= 5.0

    # Speaking
    time.sleep(0.01)
    mgr.start_speaking("elevenlabs-pcm")
    assert mgr.state == VoiceTurnState.SPEAKING
    assert turn.tts_provider == "elevenlabs-pcm"
    assert turn.ttfa_ms is not None
    assert turn.ttfa_ms >= 10.0

    # Audio chunk emission
    mgr.record_audio_chunk()
    mgr.record_audio_chunk()
    assert turn.audio_chunks_sent == 2

    # Clean finish
    completed = mgr.finish_turn()
    assert mgr.state == VoiceTurnState.IDLE
    assert completed is not None
    assert completed.completed_at is not None
    assert completed.is_cancelled is False
    assert len(mgr.history) == 1


def test_barge_in_interruption_during_speaking():
    mgr = VoiceLifecycleManager("test-session")
    mgr.start_listening(generation=1)
    mgr.mark_speech_detected()
    mgr.start_transcribing()
    mgr.finish_transcribing("Long user speech", "mock")
    mgr.start_thinking()
    mgr.start_speaking("elevenlabs")
    mgr.record_audio_chunk()

    assert mgr.state == VoiceTurnState.SPEAKING
    assert mgr.is_generation_valid(1) is True

    # User barges in!
    new_gen, cancelled = mgr.trigger_barge_in(target_generation=2)

    assert new_gen == 2
    assert mgr.current_generation == 2
    assert mgr.is_generation_valid(1) is False
    assert mgr.is_generation_valid(2) is True
    assert mgr.state == VoiceTurnState.RECOVERING

    assert cancelled is not None
    assert cancelled.is_cancelled is True
    assert cancelled.cancellation_reason == "BARGE_IN_USER_INTERRUPT"
    assert cancelled.interrupted_at is not None
    assert cancelled.barge_in_latency_ms is not None
    assert cancelled.barge_in_latency_ms >= 0.0


def test_generation_monotonicity_and_stale_rejection():
    mgr = VoiceLifecycleManager("test-session")
    mgr.start_listening(generation=5)
    assert mgr.current_generation == 5

    # If an older generation attempts to start, it should clamp to at least current_gen
    mgr.start_listening(generation=3)
    assert mgr.current_generation >= 5

    # Barge-in without explicit target should bump by 1
    new_gen, _ = mgr.trigger_barge_in()
    assert new_gen == mgr.current_generation
    assert new_gen > 5


def test_lifecycle_status_dict():
    mgr = VoiceLifecycleManager("test-session")
    mgr.start_listening(generation=10)
    status = mgr.get_status()
    assert status["session_id"] == "test-session"
    assert status["state"] == "listening"
    assert status["current_generation"] == 10
    assert status["active_turn"] is not None
    assert status["active_turn"]["generation_id"] == 10
