from __future__ import annotations

import io
import math
import struct
import wave

from .errors import HinaaError

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2
CHANNELS = 1


def validate_wav(data: bytes, *, max_seconds: float) -> bytes:
    try:
        with wave.open(io.BytesIO(data), "rb") as source:
            if (
                source.getnchannels() != CHANNELS
                or source.getsampwidth() != SAMPLE_WIDTH
                or source.getframerate() != SAMPLE_RATE
                or source.getcomptype() != "NONE"
            ):
                raise HinaaError(
                    "AUDIO_FORMAT_UNSUPPORTED",
                    "Use 16 kHz, 16-bit, mono PCM WAV audio.",
                    415,
                    user_action_required=True,
                )
            duration = source.getnframes() / source.getframerate()
            if duration <= 0:
                raise HinaaError("AUDIO_NO_SIGNAL", "No audio was captured.", 422, True, True)
            if duration > max_seconds:
                raise HinaaError(
                    "AUDIO_DURATION_EXCEEDED",
                    f"Recording must be {max_seconds:g} seconds or shorter.",
                    413,
                    user_action_required=True,
                )
            return source.readframes(source.getnframes())
    except HinaaError:
        raise
    except (wave.Error, EOFError) as error:
        raise HinaaError(
            "AUDIO_FORMAT_UNSUPPORTED",
            "The recording is not a valid PCM WAV file.",
            415,
            user_action_required=True,
        ) from error


def synthesize_mock_wav(text: str) -> bytes:
    return synthesize_placeholder_wav(text, voice_style="neutral")


def pcm_to_wav(pcm: bytes) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(CHANNELS)
        target.setsampwidth(SAMPLE_WIDTH)
        target.setframerate(SAMPLE_RATE)
        target.writeframes(pcm)
    return output.getvalue()


def synthesize_placeholder_wav(text: str, *, voice_style: str = "neutral") -> bytes:
    """Fast offline placeholder voice with distinct Hinaa/Hiro timbre.

    This is not intelligible TTS. It exists so animation/playback/latency paths
    stay testable without cloud calls while real local engines are optional.
    """
    duration = min(4.8, max(0.45, len(text) * 0.034))
    if voice_style == "hinaa":
        base_hz, brightness, tremolo = 220.0, 0.34, 4.6
    elif voice_style == "hiro":
        base_hz, brightness, tremolo = 145.0, 0.22, 3.8
    else:
        base_hz, brightness, tremolo = 185.0, 0.28, 3.2
    frames = bytearray()
    for index in range(int(SAMPLE_RATE * duration)):
        time = index / SAMPLE_RATE
        envelope = min(1.0, time * 10, (duration - time) * 10)
        syllable = 0.34 + 0.66 * abs(math.sin(time * math.pi * tremolo))
        vowel_sweep = 1 + 0.035 * math.sin(time * math.pi * 1.7)
        fundamental = math.sin(2 * math.pi * base_hz * vowel_sweep * time)
        harmonic = brightness * math.sin(2 * math.pi * base_hz * 2.01 * time)
        breath = 0.08 * math.sin(2 * math.pi * 47 * time)
        value = int(2900 * envelope * syllable * (fundamental + harmonic + breath))
        frames.extend(struct.pack("<h", value))
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(CHANNELS)
        target.setsampwidth(SAMPLE_WIDTH)
        target.setframerate(SAMPLE_RATE)
        target.writeframes(frames)
    return output.getvalue()
