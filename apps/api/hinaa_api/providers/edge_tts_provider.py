"""Edge Neural TTS Provider for HINAA (unlimited, zero-invoice, cute feminine neural voices).

Uses Microsoft Edge Neural Voices via `edge-tts`:
- English cute/bright female: `en-US-AnaNeural`, `en-US-AvaMultilingualNeural`, `en-US-JennyNeural`
- Hindi female: `hi-IN-SwaraNeural`
- Nepali female: `ne-NP-HemkalaNeural`
"""

from __future__ import annotations

import logging
import re
from time import perf_counter

import edge_tts

from .base import ProviderResult, TTSProvider

logger = logging.getLogger("hinaa.edge_tts")

DEFAULT_CUTE_GIRL_VOICE = "en-US-AnaNeural"
NEPALI_FEMALE_VOICE = "ne-NP-HemkalaNeural"
HINDI_FEMALE_VOICE = "hi-IN-SwaraNeural"

_NEPALI_SCRIPT_MARKERS = ("मलाई", "तिमी", "तपाईं", "हजुर", "हुन्छ", "गर्ने", "कस्तो", "कसरी", "छु", "छ")
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


def pick_edge_voice(text: str, requested_voice: str | None = None, companion_id: str = "hinaa") -> str:
    req = (requested_voice or "").strip()
    if req.startswith(("en-", "hi-", "ne-", "ja-", "ko-")):
        return req
    if companion_id == "hiro":
        if _DEVANAGARI_RE.search(text or ""):
            return "hi-IN-MadhurNeural"
        return "en-US-AndrewMultilingualNeural"
    if _DEVANAGARI_RE.search(text or ""):
        if any(tok in (text or "") for tok in _NEPALI_SCRIPT_MARKERS):
            return NEPALI_FEMALE_VOICE
        return HINDI_FEMALE_VOICE
    return DEFAULT_CUTE_GIRL_VOICE


class EdgeNeuralTTSProvider(TTSProvider):
    id: str = "edge-tts"

    def __init__(self, *, default_voice: str = DEFAULT_CUTE_GIRL_VOICE, pitch: str = "+4Hz", rate: str = "+6%") -> None:
        self._default_voice = default_voice
        self._pitch = pitch
        self._rate = rate

    async def synthesize(self, text: str, voice: str = "", *, companion_id: str = "hinaa") -> ProviderResult[bytes]:
        started = perf_counter()
        clean = (text or "").strip() or "Hi there!"
        chosen_voice = pick_edge_voice(clean, voice or self._default_voice, companion_id=companion_id)
        comm = edge_tts.Communicate(clean, chosen_voice, pitch=self._pitch, rate=self._rate)
        audio_parts: list[bytes] = []
        async for chunk in comm.stream():
            if chunk.get("type") == "audio" and isinstance(chunk.get("data"), (bytes, bytearray)):
                audio_parts.append(bytes(chunk["data"]))
        audio_bytes = b"".join(audio_parts)
        if not audio_bytes:
            raise RuntimeError(f"Edge TTS returned empty audio stream for voice '{chosen_voice}'.")
        latency_ms = int((perf_counter() - started) * 1000)
        return ProviderResult(audio_bytes, f"edge-tts:{chosen_voice}", latency_ms)
