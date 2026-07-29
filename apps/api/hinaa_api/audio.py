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
    duration = min(4.0, max(0.45, len(text) * 0.032))
    frames = bytearray()
    for index in range(int(SAMPLE_RATE * duration)):
        time = index / SAMPLE_RATE
        envelope = min(1.0, time * 10, (duration - time) * 10)
        syllable = 0.35 + 0.65 * abs(math.sin(time * math.pi * 3.2))
        value = int(3100 * envelope * syllable * math.sin(2 * math.pi * 185 * time))
        frames.extend(struct.pack("<h", value))
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(CHANNELS)
        target.setsampwidth(SAMPLE_WIDTH)
        target.setframerate(SAMPLE_RATE)
        target.writeframes(frames)
    return output.getvalue()
