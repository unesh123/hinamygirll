"""The run ledger is the audit trail for "did she actually stop?".

These tests pin the contract the stop-fix is judged by: a turn row carries a
start time, the delivered response, and a stop/idle timestamp; a TTS row carries
the provider, voice, model, latency and outcome; and a ledger that cannot open is
inert instead of fatal.
"""
from __future__ import annotations

import time
from pathlib import Path

from hinaa_api.run_ledger import RunLedger


def test_turn_start_stop_roundtrip(tmp_path: Path) -> None:
    ledger = RunLedger(tmp_path / "ledger.db")
    assert ledger.available is True

    ledger.record_turn_start("turn-1", session_id="session-1", provider="mock")
    time.sleep(0.01)
    ledger.record_turn_stop("turn-1", response_text="Hello  there,\n friend", status="completed")

    rows = ledger.recent_turns(5)
    assert len(rows) == 1
    row = rows[0]
    assert row.turn_id == "turn-1"
    assert row.session_id == "session-1"
    assert row.status == "completed"
    # The stop/idle timestamp exists and is not before the start.
    assert row.stopped_at is not None
    assert row.stopped_at >= row.started_at
    assert row.duration_ms is not None and row.duration_ms >= 0
    # The delivered response is stored, whitespace-collapsed.
    assert row.response_preview == "Hello there, friend"


def test_aborted_turn_is_recorded_as_aborted(tmp_path: Path) -> None:
    ledger = RunLedger(tmp_path / "ledger.db")
    ledger.record_turn_start("turn-2", session_id="s")
    ledger.record_turn_stop("turn-2", response_text=None, status="aborted")
    rows = ledger.recent_turns(5)
    assert rows[0].status == "aborted"
    assert rows[0].stopped_at is not None


def test_tts_events_are_traceable(tmp_path: Path) -> None:
    ledger = RunLedger(tmp_path / "ledger.db")
    ledger.record_tts(
        provider="elevenlabs",
        voice_id="WUgmmuDCpFXQ4z0NUUYX",
        model_id="eleven_turbo_v2_5",
        output_format="mp3_44100_128",
        latency_ms=412,
        ok=False,
        error="quota_exceeded: 3 credits remaining",
        turn_id="turn-1",
    )
    ledger.record_tts(
        provider="deepgram-fallback",
        voice_id="aura-2-thalia-en",
        model_id="aura-2-thalia-en",
        output_format="mp3",
        latency_ms=380,
        ok=True,
        audio_bytes=14733,
        turn_id="turn-1",
    )
    events = ledger.recent_tts(10)
    assert len(events) == 2
    newest = events[0]
    assert newest["provider"] == "deepgram-fallback"
    assert newest["ok"] == 1
    assert newest["audioBytes"] == 14733
    failed = events[1]
    assert failed["ok"] == 0
    assert "quota_exceeded" in (failed["error"] or "")


def test_motion_events_are_recorded(tmp_path: Path) -> None:
    ledger = RunLedger(tmp_path / "ledger.db")
    ledger.record_motion(state="idle", session_id="s", detail="reply delivered")
    events = ledger.recent_motion(10)
    assert events and events[0]["state"] == "idle"
    assert events[0]["detail"] == "reply delivered"


def test_unopenable_ledger_is_inert(tmp_path: Path) -> None:
    # A file used as a directory makes opening impossible; the ledger must not
    # raise, and every read must come back empty.
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    ledger = RunLedger(blocker / "ledger.db")
    assert ledger.available is False
    ledger.record_turn_start("t", session_id="s")
    ledger.record_tts(
        provider="x", voice_id="v", model_id="m", output_format="mp3", latency_ms=1, ok=True
    )
    assert ledger.recent_turns() == []
    assert ledger.recent_tts() == []
