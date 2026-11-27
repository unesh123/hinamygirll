"""Offline audio onset and BPM estimation (WAV + FFmpeg fallback, pure NumPy)."""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np


def _decode_wav_mono(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sample_rate <= 0 or n_frames <= 0:
        raise ValueError("Audio stream is empty.")

    if sample_width == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sample_width == 2:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 4:
        samples = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sample_width} bytes.")

    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, int(sample_rate)


def detect_beats_pcm(samples: np.ndarray, sample_rate: int) -> dict[str, Any]:
    """Detect beat onset timestamps and estimated BPM from mono float32 PCM samples."""
    if sample_rate <= 0 or samples.size == 0:
        raise ValueError("Cannot detect beats on empty PCM audio.")

    duration_seconds = float(samples.size) / float(sample_rate)
    hop = max(128, int(sample_rate * 0.01))  # 10ms envelope frames
    n_hops = samples.size // hop
    if n_hops < 4:
        return {
            "bpm": 0.0,
            "beat_times_sec": [],
            "onset_strengths": [],
            "duration_seconds": round(duration_seconds, 3),
        }

    frames = samples[: n_hops * hop].reshape(n_hops, hop)
    rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
    diff = np.maximum(0.0, np.diff(rms, prepend=rms[0]))
    hop_dt = float(hop) / float(sample_rate)

    # Adaptive local threshold + refractory window (>= 220ms between beats)
    peak_floor = max(float(np.mean(diff) + 1.4 * np.std(diff)), float(np.max(diff)) * 0.25, 1e-4)
    min_gap_hops = max(2, int(round(0.22 / hop_dt)))

    beat_indices: list[int] = []
    for idx in range(1, n_hops - 1):
        val = float(diff[idx])
        if val < peak_floor:
            continue
        if val >= float(diff[idx - 1]) and val >= float(diff[idx + 1]):
            if not beat_indices or (idx - beat_indices[-1]) >= min_gap_hops:
                beat_indices.append(idx)
            elif val > float(diff[beat_indices[-1]]):
                beat_indices[-1] = idx

    beat_times = [round(i * hop_dt, 3) for i in beat_indices]
    strengths = [round(float(diff[i]), 4) for i in beat_indices]

    bpm = 0.0
    if len(beat_indices) >= 2:
        intervals = np.diff(np.array(beat_indices, dtype=np.float64) * hop_dt)
        valid = intervals[(intervals >= 0.24) & (intervals <= 1.8)]
        if valid.size > 0:
            median_ibi = float(np.median(valid))
            if median_ibi > 0:
                bpm = round(60.0 / median_ibi, 2)

    return {
        "bpm": bpm,
        "beat_times_sec": beat_times,
        "onset_strengths": strengths,
        "duration_seconds": round(duration_seconds, 3),
    }


def detect_beats_wav(wav_bytes: bytes) -> dict[str, Any]:
    """Detect beats directly from in-memory WAV bytes."""
    samples, sr = _decode_wav_mono(wav_bytes)
    return detect_beats_pcm(samples, sr)


def detect_beats_file(audio_path: str | Path) -> dict[str, Any]:
    """Detect beats from WAV directly or any audio/video file via FFmpeg PCM conversion."""
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")
    if path.suffix.lower() == ".wav":
        return detect_beats_wav(path.read_bytes())
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required to decode non-WAV audio files.")
    with tempfile.TemporaryDirectory(prefix="hinaa-beats-") as tmp:
        out_wav = Path(tmp) / "mono.wav"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-nostdin",
                "-v",
                "error",
                "-i",
                str(path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "22050",
                "-f",
                "wav",
                str(out_wav),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return detect_beats_wav(out_wav.read_bytes())


__all__ = [
    "detect_beats_file",
    "detect_beats_pcm",
    "detect_beats_wav",
]
