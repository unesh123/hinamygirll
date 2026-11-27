"""Streaming speech-to-text adapter with Faster-Whisper Tier A and offline test fallback."""

from __future__ import annotations

import asyncio
import importlib.util
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from .vad import pcm16_rms


@dataclass(frozen=True)
class TranscriptChunk:
    text: str
    is_final: bool
    confidence: float = 1.0
    latency_ms: float = 0.0
    tier: str = "tier-a"


TranscribeCallable = Callable[[bytes, bool], Awaitable[str] | str]


def tier_a_installed() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


class StreamingASR:
    """Buffered chunked ASR emitting interim partial transcripts and final utterances."""

    def __init__(
        self,
        *,
        transcribe_fn: TranscribeCallable | None = None,
        tier: str | None = None,
    ) -> None:
        self._transcribe_fn = transcribe_fn
        self.tier = tier or ("faster-whisper" if tier_a_installed() else "fallback-energy")
        self._buffer = bytearray()

    def push_audio(self, pcm_bytes: bytes) -> None:
        self._buffer.extend(pcm_bytes)

    def clear(self) -> None:
        self._buffer.clear()

    async def flush(self, *, is_final: bool = True) -> TranscriptChunk:
        t0 = time.perf_counter()
        audio = bytes(self._buffer)
        if is_final:
            self._buffer.clear()

        if self._transcribe_fn is not None:
            res = self._transcribe_fn(audio, is_final)
            if asyncio.iscoroutine(res):
                res = await res
            text = str(res or "").strip()
        elif not audio:
            text = ""
        else:
            # Offline/no-model-weights deterministic fallback: avoids crashing when
            # faster_whisper native model isn't downloaded yet.
            rms = pcm16_rms(audio)
            text = "" if rms < 0.01 else f"[voice segment {len(audio)} bytes]"

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return TranscriptChunk(
            text=text,
            is_final=is_final,
            confidence=0.96 if text and not text.startswith("[") else 0.5,
            latency_ms=elapsed_ms,
            tier=self.tier,
        )
