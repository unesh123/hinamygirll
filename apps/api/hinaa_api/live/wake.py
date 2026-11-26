"""Wake-word hook, live session state clock, and noise suppression helpers."""

from __future__ import annotations

import array
import time
from dataclasses import dataclass

from .vad import pcm16_rms


class NoiseSuppressor:
    """Zero-dependency high-pass pre-emphasis + soft noise gate on 16kHz int16 PCM."""

    def __init__(self, *, alpha: float = 0.94, gate_rms: float = 0.008) -> None:
        self.alpha = alpha
        self.gate_rms = gate_rms
        self._prev_sample = 0

    def process(self, frame: bytes) -> bytes:
        if len(frame) < 2:
            return frame
        if pcm16_rms(frame) < self.gate_rms:
            return b"\x00" * len(frame)
        usable = len(frame) - (len(frame) % 2)
        samples = array.array("h")
        samples.frombytes(frame[:usable])
        out = array.array("h", [0] * len(samples))
        prev = self._prev_sample
        for i, cur in enumerate(samples):
            val = int(cur - self.alpha * prev)
            out[i] = max(-32768, min(32767, val))
            prev = cur
        self._prev_sample = prev
        return out.tobytes()


class WakeWordDetector:
    """Wake-word gate matching configured phrase ('Hey Hina') cleanly."""

    def __init__(self, phrase: str = "hey hina") -> None:
        self.phrase = phrase.strip().lower()

    def matches_transcript(self, text: str) -> bool:
        norm = " ".join(str(text or "").lower().split())
        return self.phrase in norm or "hey hinaa" in norm


@dataclass
class LiveSessionLifecycle:
    idle_timeout_seconds: float = 30.0
    state: str = "idle"
    last_activity_ts: float = 0.0

    def wake(self, *, now: float | None = None) -> str:
        self.state = "listening"
        self.last_activity_ts = time.monotonic() if now is None else now
        return self.state

    def transition(self, next_state: str, *, now: float | None = None) -> str:
        self.state = next_state
        self.last_activity_ts = time.monotonic() if now is None else now
        return self.state

    def tick(self, *, now: float | None = None) -> str:
        if self.state == "idle":
            return self.state
        cur = time.monotonic() if now is None else now
        if self.last_activity_ts and (cur - self.last_activity_ts) >= self.idle_timeout_seconds:
            self.state = "idle"
        return self.state
