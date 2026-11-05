"""
HINAA OS — Speech Turn Coordinator & Exactly-Once Delivery Engine (Module F)
Coordinates audio segment generation, enforces monotonic generation IDs,
derives deterministic idempotency keys, reorders out-of-order chunks,
and executes instantaneous barge-in cancellation across active and queued speech.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

from .contracts import (
    ClaimPerspective,
    DeliveryMode,
    SpokenSegment,
    TurnState,
    compute_segment_idempotency_key,
)

logger = logging.getLogger("hinaa.explanation.coordinator")


@dataclass(slots=True)
class SegmentTelemetry:
    segment_id: str
    idempotency_key: str
    generation_id: int
    segment_index: int
    state: TurnState
    enqueue_count: int = 1
    play_count: int = 0
    created_at: float = field(default_factory=time.time)
    played_at: Optional[float] = None
    cancelled_at: Optional[float] = None
    cancel_reason: Optional[str] = None


@dataclass(slots=True)
class TurnSession:
    conversation_id: str
    response_id: str
    generation_id: int = 1
    active_segment_id: Optional[str] = None
    state: TurnState = TurnState.CREATED
    delivery_mode: DeliveryMode = DeliveryMode.EXPLAIN_BRIEFLY
    segments: List[SpokenSegment] = field(default_factory=list)
    reorder_buffer: Dict[int, SpokenSegment] = field(default_factory=dict)
    next_expected_index: int = 0
    enqueued_keys: Set[str] = field(default_factory=set)
    played_keys: Set[str] = field(default_factory=set)
    telemetry: Dict[str, SegmentTelemetry] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class SpeechTurnCoordinator:
    """Authoritative coordinator for audio generation, playback, and barge-in."""

    def __init__(self) -> None:
        self._sessions: Dict[str, TurnSession] = {}
        self._lock = asyncio.Lock()

    def get_or_create_session(
        self,
        conversation_id: str,
        response_id: str,
        delivery_mode: DeliveryMode = DeliveryMode.EXPLAIN_BRIEFLY,
    ) -> TurnSession:
        if conversation_id not in self._sessions:
            self._sessions[conversation_id] = TurnSession(
                conversation_id=conversation_id,
                response_id=response_id,
                delivery_mode=delivery_mode,
            )
        session = self._sessions[conversation_id]
        if session.response_id != response_id:
            session.response_id = response_id
            session.generation_id += 1
            session.segments.clear()
            session.reorder_buffer.clear()
            session.next_expected_index = 0
            session.delivery_mode = delivery_mode
        return session

    def plan_segments(
        self,
        conversation_id: str,
        response_id: str,
        script: str,
        delivery_mode: DeliveryMode = DeliveryMode.EXPLAIN_BRIEFLY,
    ) -> List[SpokenSegment]:
        """Splits composed script into digestible spoken segments with deterministic idempotency keys."""
        session = self.get_or_create_session(conversation_id, response_id, delivery_mode)
        session.state = TurnState.PLANNED

        # Split into sentences or thought groups
        raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
        if not raw_sentences:
            raw_sentences = [script.strip()] if script.strip() else []

        segments: List[SpokenSegment] = []
        for idx, sentence in enumerate(raw_sentences):
            seg_id = f"seg-{session.generation_id}-{idx:03d}"
            idem_key = compute_segment_idempotency_key(
                conversation_id=conversation_id,
                response_id=response_id,
                generation_id=session.generation_id,
                segment_index=idx,
                text=sentence,
            )
            # Estimate duration (~3.2 words per second)
            word_count = len(sentence.split())
            duration = max(1.5, word_count / 3.2)

            segment = SpokenSegment(
                segment_id=seg_id,
                segment_index=idx,
                text=sentence,
                perspectives=[ClaimPerspective.SOURCE_SUPPORTED],
                expected_duration_seconds=duration,
                idempotency_key=idem_key,
                generation_id=session.generation_id,
                state=TurnState.PLANNED,
            )
            segments.append(segment)

            session.telemetry[seg_id] = SegmentTelemetry(
                segment_id=seg_id,
                idempotency_key=idem_key,
                generation_id=session.generation_id,
                segment_index=idx,
                state=TurnState.PLANNED,
            )

        session.segments = list(segments)
        return segments

    def enqueue_segment(
        self,
        conversation_id: str,
        segment: SpokenSegment,
    ) -> bool:
        """Enqueues segment with strict idempotency. Returns False if already enqueued or stale."""
        session = self._sessions.get(conversation_id)
        if not session:
            return False

        # Drop stale segments from older generation
        if segment.generation_id < session.generation_id:
            logger.warning(
                "Dropping stale segment %s (generation %d < active %d)",
                segment.segment_id, segment.generation_id, session.generation_id
            )
            return False

        # Track telemetry
        if segment.segment_id not in session.telemetry:
            session.telemetry[segment.segment_id] = SegmentTelemetry(
                segment_id=segment.segment_id,
                idempotency_key=segment.idempotency_key,
                generation_id=segment.generation_id,
                segment_index=segment.segment_index,
                state=TurnState.CREATED,
            )

        # Track segment in session if not present
        if segment not in session.segments:
            session.segments.append(segment)

        # Exactly-once guarantee: drop if already enqueued or played
        if segment.idempotency_key in session.enqueued_keys or segment.idempotency_key in session.played_keys:
            telem = session.telemetry.get(segment.segment_id)
            if telem:
                telem.enqueue_count += 1
            logger.info("Idempotent deduplication: segment %s already enqueued", segment.segment_id)
            return False

        session.enqueued_keys.add(segment.idempotency_key)
        segment.state = TurnState.QUEUED
        session.state = TurnState.QUEUED
        telem = session.telemetry.get(segment.segment_id)
        if telem:
            telem.state = TurnState.QUEUED
        return True

    def process_incoming_chunk(
        self,
        conversation_id: str,
        segment: SpokenSegment,
    ) -> List[SpokenSegment]:
        """Buffers out-of-order chunks and releases them sequentially in strict ascending index."""
        session = self._sessions.get(conversation_id)
        if not session:
            return []

        if segment.generation_id < session.generation_id:
            return []

        # Buffer chunk
        session.reorder_buffer[segment.segment_index] = segment

        # Release consecutive ready chunks
        ready: List[SpokenSegment] = []
        while session.next_expected_index in session.reorder_buffer:
            ready_seg = session.reorder_buffer.pop(session.next_expected_index)
            ready.append(ready_seg)
            session.next_expected_index += 1

        return ready

    def mark_playing(self, conversation_id: str, segment: SpokenSegment) -> None:
        session = self._sessions.get(conversation_id)
        if session and segment.generation_id == session.generation_id:
            session.active_segment_id = segment.segment_id
            session.state = TurnState.PLAYING
            segment.state = TurnState.PLAYING
            telem = session.telemetry.get(segment.segment_id)
            if telem:
                telem.state = TurnState.PLAYING

    def mark_played(self, conversation_id: str, segment: SpokenSegment) -> bool:
        """Records completed playback. Returns False if duplicate or stale."""
        session = self._sessions.get(conversation_id)
        if not session:
            return False

        if segment.generation_id < session.generation_id:
            return False

        if segment.idempotency_key in session.played_keys:
            return False

        session.played_keys.add(segment.idempotency_key)
        segment.state = TurnState.PLAYED
        telem = session.telemetry.get(segment.segment_id)
        if telem:
            telem.play_count += 1
            telem.state = TurnState.PLAYED
            telem.played_at = time.time()

        # Check if all segments played
        if session.segments and all(s.state == TurnState.PLAYED for s in session.segments):
            session.state = TurnState.PLAYED
            session.active_segment_id = None

        return True

    def barge_in(self, conversation_id: str, reason: str = "user_speech_detected") -> int:
        """Executes instantaneous barge-in: increments generation, cancels pending speech, drains queues."""
        session = self._sessions.get(conversation_id)
        if not session:
            return 1

        session.generation_id += 1
        new_gen = session.generation_id
        session.state = TurnState.CANCELLED
        session.active_segment_id = None

        # Drain reorder buffer and cancel all unplayed segments
        session.reorder_buffer.clear()
        now = time.time()
        for seg in session.segments:
            seg.state = TurnState.CANCELLED
            telem = session.telemetry.get(seg.segment_id)
            if telem:
                telem.state = TurnState.CANCELLED
                telem.cancelled_at = now
                telem.cancel_reason = reason

        logger.info(
            "Barge-in executed for conversation %s: generation advanced to %d, reason: %s",
            conversation_id, new_gen, reason
        )
        return new_gen

    def get_telemetry(self, conversation_id: str) -> Dict[str, Any]:
        session = self._sessions.get(conversation_id)
        if not session:
            return {}
        return {
            "conversation_id": session.conversation_id,
            "response_id": session.response_id,
            "generation_id": session.generation_id,
            "state": session.state.value,
            "delivery_mode": session.delivery_mode.value,
            "segments_count": len(session.segments),
            "enqueued_count": len(session.enqueued_keys),
            "played_count": len(session.played_keys),
            "segments": {k: {
                "state": v.state.value,
                "enqueue_count": v.enqueue_count,
                "play_count": v.play_count,
                "cancel_reason": v.cancel_reason,
            } for k, v in session.telemetry.items()},
        }
