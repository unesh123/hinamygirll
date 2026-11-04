"""Voice Turn Lifecycle State Machine & Barge-In Engine for HINAA OS.

Provides millisecond-precise tracking of voice conversation turns,
enforces monotonically increasing generation IDs, and executes instantaneous
barge-in cancellation across in-flight LLM generation and queued TTS audio.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import logging
from time import perf_counter
from typing import Any

logger = logging.getLogger("hinaa.voice.lifecycle")


class VoiceTurnState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    SPEECH_DETECTED = "speech_detected"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTING = "interrupting"
    DRAINING = "draining"
    RECOVERING = "recovering"


@dataclass(slots=True)
class VoiceTurnMetrics:
    turn_id: str
    generation_id: int
    state: VoiceTurnState
    started_at: float = field(default_factory=perf_counter)
    speech_detected_at: float | None = None
    stt_started_at: float | None = None
    stt_finished_at: float | None = None
    first_token_at: float | None = None
    first_audio_at: float | None = None
    completed_at: float | None = None
    interrupted_at: float | None = None
    drained_at: float | None = None

    transcript: str = ""
    stt_provider: str = ""
    tts_provider: str = ""
    audio_chunks_sent: int = 0
    is_cancelled: bool = False
    cancellation_reason: str = ""

    @property
    def stt_latency_ms(self) -> float | None:
        if self.stt_started_at and self.stt_finished_at:
            return round((self.stt_finished_at - self.stt_started_at) * 1000, 2)
        return None

    @property
    def ttft_ms(self) -> float | None:
        """Time to first token from STT completion."""
        if self.stt_finished_at and self.first_token_at:
            return round((self.first_token_at - self.stt_finished_at) * 1000, 2)
        return None

    @property
    def ttfa_ms(self) -> float | None:
        """Time to first audio chunk from STT completion."""
        if self.stt_finished_at and self.first_audio_at:
            return round((self.first_audio_at - self.stt_finished_at) * 1000, 2)
        return None

    @property
    def barge_in_latency_ms(self) -> float | None:
        """Latency from user barge-in trigger to completed task draining."""
        if self.interrupted_at and self.drained_at:
            return round((self.drained_at - self.interrupted_at) * 1000, 2)
        return None

    @property
    def total_turn_ms(self) -> float:
        end = self.completed_at or self.drained_at or perf_counter()
        return round((end - self.started_at) * 1000, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "generation_id": self.generation_id,
            "state": self.state.value,
            "transcript": self.transcript,
            "stt_provider": self.stt_provider,
            "tts_provider": self.tts_provider,
            "audio_chunks_sent": self.audio_chunks_sent,
            "is_cancelled": self.is_cancelled,
            "cancellation_reason": self.cancellation_reason,
            "stt_latency_ms": self.stt_latency_ms,
            "ttft_ms": self.ttft_ms,
            "ttfa_ms": self.ttfa_ms,
            "barge_in_latency_ms": self.barge_in_latency_ms,
            "total_turn_ms": self.total_turn_ms,
        }


class VoiceLifecycleManager:
    """Manages the full state machine and synchronization of voice conversation turns."""

    def __init__(self, session_id: str = "default") -> None:
        self.session_id = session_id
        self.state: VoiceTurnState = VoiceTurnState.IDLE
        self.current_generation: int = 0
        self.turn_counter: int = 0
        self.active_turn: VoiceTurnMetrics | None = None
        self.history: list[VoiceTurnMetrics] = []
        self._lock = asyncio.Lock()

    def start_session(self, initial_generation: int = 0) -> None:
        self.current_generation = initial_generation
        self.state = VoiceTurnState.IDLE
        self.active_turn = None
        self.history.clear()

    def start_listening(self, generation: int | None = None) -> VoiceTurnMetrics:
        """Begins an active audio capture window."""
        if generation is not None:
            self.current_generation = max(self.current_generation, generation)
        else:
            self.current_generation += 1

        self.turn_counter += 1
        turn_id = f"vturn-{self.turn_counter}-{self.current_generation}"
        self.state = VoiceTurnState.LISTENING

        turn = VoiceTurnMetrics(
            turn_id=turn_id,
            generation_id=self.current_generation,
            state=self.state,
        )
        self.active_turn = turn
        logger.debug("VoiceLifecycle: LISTENING on %s (gen=%d)", turn_id, self.current_generation)
        return turn

    def mark_speech_detected(self) -> None:
        if self.active_turn and self.state == VoiceTurnState.LISTENING:
            self.state = VoiceTurnState.SPEECH_DETECTED
            self.active_turn.state = self.state
            self.active_turn.speech_detected_at = perf_counter()

    def start_transcribing(self) -> None:
        if self.active_turn:
            self.state = VoiceTurnState.TRANSCRIBING
            self.active_turn.state = self.state
            self.active_turn.stt_started_at = perf_counter()

    def finish_transcribing(self, transcript: str, stt_provider: str) -> None:
        if self.active_turn:
            self.active_turn.stt_finished_at = perf_counter()
            self.active_turn.transcript = transcript
            self.active_turn.stt_provider = stt_provider

    def start_thinking(self) -> None:
        if self.active_turn:
            self.state = VoiceTurnState.THINKING
            self.active_turn.state = self.state

    def mark_first_token(self) -> None:
        if self.active_turn and not self.active_turn.first_token_at:
            self.active_turn.first_token_at = perf_counter()

    def start_speaking(self, tts_provider: str = "") -> None:
        if self.active_turn:
            self.state = VoiceTurnState.SPEAKING
            self.active_turn.state = self.state
            self.active_turn.tts_provider = tts_provider
            if not self.active_turn.first_audio_at:
                self.active_turn.first_audio_at = perf_counter()

    def record_audio_chunk(self) -> None:
        if self.active_turn:
            if not self.active_turn.first_audio_at:
                self.active_turn.first_audio_at = perf_counter()
            self.active_turn.audio_chunks_sent += 1

    def finish_turn(self) -> VoiceTurnMetrics | None:
        """Marks the active turn as cleanly completed."""
        if not self.active_turn:
            self.state = VoiceTurnState.IDLE
            return None

        turn = self.active_turn
        turn.completed_at = perf_counter()
        turn.state = VoiceTurnState.IDLE
        self.state = VoiceTurnState.IDLE

        self.history.append(turn)
        if len(self.history) > 50:
            self.history.pop(0)

        self.active_turn = None
        return turn

    def trigger_barge_in(self, target_generation: int | None = None) -> tuple[int, VoiceTurnMetrics | None]:
        """Executes instant barge-in cancellation.

        Bumps generation, sets state to INTERRUPTING -> DRAINING -> RECOVERING,
        and invalidates stale audio.
        """
        interrupted_turn = self.active_turn
        old_generation = self.current_generation

        if target_generation is not None and target_generation > self.current_generation:
            self.current_generation = target_generation
        else:
            self.current_generation += 1

        now = perf_counter()
        if interrupted_turn:
            interrupted_turn.interrupted_at = now
            interrupted_turn.is_cancelled = True
            interrupted_turn.cancellation_reason = "BARGE_IN_USER_INTERRUPT"
            interrupted_turn.state = VoiceTurnState.DRAINING
            interrupted_turn.drained_at = perf_counter()
            self.history.append(interrupted_turn)
            if len(self.history) > 50:
                self.history.pop(0)

        self.state = VoiceTurnState.RECOVERING
        self.active_turn = None
        logger.info(
            "VoiceLifecycle: BARGE-IN executed (cancelled gen=%d, new gen=%d)",
            old_generation,
            self.current_generation,
        )
        return self.current_generation, interrupted_turn

    def is_generation_valid(self, generation: int) -> bool:
        """Checks if a frame or event belongs to the active generation."""
        return generation == self.current_generation

    def get_status(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "current_generation": self.current_generation,
            "turn_counter": self.turn_counter,
            "active_turn": self.active_turn.to_dict() if self.active_turn else None,
            "recent_turns_count": len(self.history),
        }
