"""Measured audio accents and reference cuts. These are estimates, never lyric transcription."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np


def _ffmpeg(args: list[str]) -> bytes:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise ValueError("FFmpeg is required for motion-media analysis")
    result = subprocess.run(  # noqa: S603 - executable resolved with shutil.which; argv only
        [exe, "-v", "error", *args], capture_output=True, timeout=60, check=False
    )
    if result.returncode:
        raise ValueError("Media analysis failed: " + result.stderr.decode(errors="replace")[-350:])
    return result.stdout


def analyze_audio(path: Path, start: float = 0, duration: float = 30) -> dict:
    """Spectral-flux onset detection; no fabricated uniform BPM grid."""
    rate, hop, window = 22050, 256, 1024
    raw = _ffmpeg(
        [
            "-ss",
            str(start),
            "-i",
            str(path),
            "-t",
            str(duration),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(rate),
            "-f",
            "f32le",
            "pipe:1",
        ]
    )
    samples = np.frombuffer(raw, dtype="<f4")
    if len(samples) < window:
        raise ValueError("Audio is too short or the selected trim has no audio")
    frames = np.lib.stride_tricks.sliding_window_view(samples, window)[::hop]
    spectra = np.abs(np.fft.rfft(frames * np.hanning(window), axis=1))
    log_mag = np.log1p(spectra)
    flux = np.maximum(0, np.diff(log_mag, axis=0, prepend=log_mag[:1])).mean(axis=1)
    flux[:2] = 0
    threshold = np.array([np.median(flux[max(0, i - 18) : i + 19]) * 1.6 for i in range(len(flux))])
    floor = max(0.0001, float(np.max(flux)) * 0.08)
    candidates = [
        i
        for i in range(1, len(flux) - 1)
        if flux[i] > max(floor, threshold[i]) and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1]
    ]
    chosen: list[int] = []
    gap = max(1, int(0.16 * rate / hop))
    for idx in sorted(candidates, key=lambda i: float(flux[i]), reverse=True):
        if all(abs(idx - j) >= gap for j in chosen):
            chosen.append(idx)
    chosen.sort()
    peak = max(float(np.max(flux)), 1e-8)
    return {
        "method": "spectral_flux_onsets",
        "source_start_seconds": start,
        "duration_seconds": round(len(samples) / rate, 4),
        "accents": [round((i * hop + window / 2) / rate, 4) for i in chosen],
        "strengths": [round(float(flux[i]) / peak, 4) for i in chosen],
        "rms": round(float(np.sqrt(np.mean(samples**2))), 5),
        "limitations": (
            "Detected transients are timing suggestions; inspect them against the music. "
            "No lyrics, word alignment, or guaranteed downbeat detection."
        ),
    }


def analyze_reference(path: Path, duration: float = 30) -> dict:
    """Low-resolution histogram changes identify candidate hard cuts; not motion transfer."""
    probe = shutil.which("ffprobe")
    if not probe:
        raise ValueError("ffprobe is required for reference analysis")
    result = subprocess.run(  # noqa: S603 - executable resolved with shutil.which; argv only
        [probe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    info = json.loads(result.stdout)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("Reference has no video stream")
    raw = _ffmpeg(
        [
            "-i",
            str(path),
            "-t",
            str(duration),
            "-vf",
            "fps=8,scale=160:90",
            "-an",
            "-pix_fmt",
            "gray",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
    )
    if len(raw) < 2 * 160 * 90:
        raise ValueError("Reference is too short to analyze")
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 90, 160)
    hist = np.array([np.histogram(f, bins=32, range=(0, 256))[0] / f.size for f in frames])
    changes = np.abs(np.diff(hist, axis=0)).sum(axis=1) / 2
    threshold = max(
        0.2, float(np.median(changes) + 4 * np.median(np.abs(changes - np.median(changes))))
    )
    candidates = np.flatnonzero(changes > threshold) + 1
    cuts: list[float] = []
    for n in candidates:
        t = round(float(n) / 8, 3)
        if not cuts or t - cuts[-1] >= 0.3:
            cuts.append(t)
    return {
        "method": "grayscale_histogram_changes_8fps",
        "width": video.get("width"),
        "height": video.get("height"),
        "frame_rate": video.get("avg_frame_rate"),
        "duration_seconds": float(info.get("format", {}).get("duration") or 0),
        "analyzed_seconds": round(len(frames) / 8, 3),
        "candidate_cuts": cuts,
        "limitations": (
            "Approximate hard cuts (125 ms sampling); flashes can trigger cuts. "
            "Does not reconstruct cameras, typography, subjects, or neural motion."
        ),
    }
