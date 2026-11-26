"""Sentence-streaming TTS queue supporting sub-400ms first-sentence audio & instant cancel."""

from __future__ import annotations

import asyncio
import importlib.util
import math
import re
import struct
import time
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def tier_a_tts_installed() -> bool:
    return (
        importlib.util.find_spec("kokoro_onnx") is not None
        or importlib.util.find_spec("piper") is not None
    )


def _synthesize_tone_pcm(text: str, *, sample_rate: int = 24000) -> bytes:
    """Generate clean, short 24kHz PCM envelope proportional to phrase length for offline tests."""
    duration_s = min(0.18, max(0.04, len(text) * 0.002))
    n_samples = int(sample_rate * duration_s)
    buf = bytearray(n_samples * 2)
    freq = 260.0
    for i in range(n_samples):
        env = math.sin(math.pi * i / max(1, n_samples - 1))
        val = int(4000 * env * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
        struct.pack_into("<h", buf, i * 2, val)
    return bytes(buf)


SynthCallable = Callable[[str], Awaitable[bytes] | bytes]


@dataclass(frozen=True)
class TtsAudioChunk:
    sentence: str
    pcm: bytes
    sample_rate: int
    latency_ms: float


class SentenceStreamer:
    """Incrementally detects complete sentences from LLM token deltas and emits PCM."""

    def __init__(
        self,
        *,
        synth_fn: SynthCallable | None = None,
        sample_rate: int = 24000,
    ) -> None:
        self._synth_fn = synth_fn
        self.sample_rate = sample_rate
        self._pending = ""
        self._cancelled = False
        self._queue: asyncio.Queue[TtsAudioChunk | None] = asyncio.Queue()

    def reset(self) -> None:
        self._pending = ""
        self._cancelled = False
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def cancel(self) -> None:
        self._cancelled = True
        self._pending = ""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._queue.put_nowait(None)

    async def _speak_sentence(self, sentence: str) -> None:
        if self._cancelled or not sentence.strip():
            return
        t0 = time.perf_counter()
        if self._synth_fn is not None:
            pcm = self._synth_fn(sentence)
            if asyncio.iscoroutine(pcm):
                pcm = await pcm
        else:
            pcm = _synthesize_tone_pcm(sentence, sample_rate=self.sample_rate)
        if self._cancelled:
            return
        await self._queue.put(
            TtsAudioChunk(
                sentence=sentence,
                pcm=bytes(pcm),
                sample_rate=self.sample_rate,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            )
        )

    async def push_token(self, token: str) -> list[str]:
        if self._cancelled or not token:
            return []
        self._pending += token
        parts = _SENTENCE_SPLIT_RE.split(self._pending)
        if len(parts) <= 1:
            return []
        emitted: list[str] = []
        for s in parts[:-1]:
            clean = s.strip()
            if clean:
                await self._speak_sentence(clean)
                emitted.append(clean)
        self._pending = parts[-1]
        return emitted

    async def finish(self) -> list[str]:
        emitted: list[str] = []
        rem = self._pending.strip()
        self._pending = ""
        if rem and not self._cancelled:
            await self._speak_sentence(rem)
            emitted.append(rem)
        await self._queue.put(None)
        return emitted

    async def stream_chunks(self) -> AsyncIterator[TtsAudioChunk]:
        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item
