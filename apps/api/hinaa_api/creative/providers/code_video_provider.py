"""Video by code — how Claude creates videos, and how Hina should too.

The user's correction, 2026-11-13: Hina must NOT need a generative video
model (fal.ai / Veo / Kling) to make a video. The frontier model writes
the video as code — a timeline of scenes, text, timing and transitions —
and a local renderer executes it with ffmpeg into a real MP4. No API key,
no credits, no per-second billing, no AI drift, no invented pixels.

That is exactly what this provider does. The brain writes a
``CodeVideoTimeline`` (JSON, validated here); this provider renders it
with ffmpeg and verifies the output with ffprobe. What code can make,
perfectly and exactly: black-screen text edits, lyric videos, slideshows,
feature showcases, ads, captions, transitions, audio mixes. What it
cannot make: new footage (a cinematic scene, a dancing character, a
fight) — that still needs real clips or a generative model, and the
provider says so instead of pretending.

Timeline contract (the model writes this JSON into the job's timeline):

    {"width": 1080, "height": 1920, "fps": 30, "scenes": [
      {"duration": 3.0, "background": "black",
       "texts": [{"text": "Sometimes you gotta run", "start": 0.5, "end": 2.8,
                  "y": "(h-text_h)/2", "size": 72, "color": "white"}],
       "transition": "crossfade"},
      {"duration": 3.0, "background": "/path/to/image.png", "texts": [...],
       "transition": "cut"}],
     "audio": "/path/to/song.mp3"}

Background is a color name/hex or a local image path. Transitions are
cut, crossfade or fadeblack. Total duration is capped at 60 s.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ...errors import HinaaError
from ..models import CreativeJobRecord, CreativeOperation
from .base import CreativeProvider

_MAX_TOTAL_SECONDS = 60.0
_MAX_SCENES = 20
_MIN_MP4_BYTES = 1024


class CodeVideoText(BaseModel):
    text: str
    start: float = 0.0
    end: float | None = None
    x: str = "(w-text_w)/2"
    y: str = "(h-text_h)/2"
    size: int = 64
    color: str = "white"
    font: str | None = None

    @field_validator("text")
    @classmethod
    def _text_must_be_real(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text must not be empty")
        if "\n" in v:
            raise ValueError("one line per text entry (no newlines)")
        return v

    @field_validator("size")
    @classmethod
    def _size_in_range(cls, v: int) -> int:
        if not 8 <= v <= 400:
            raise ValueError("size must be 8..400")
        return v


class CodeVideoScene(BaseModel):
    duration: float
    background: str = "black"
    texts: list[CodeVideoText] = Field(default_factory=list)
    transition: str = "cut"
    transition_duration: float = 0.5

    @field_validator("duration")
    @classmethod
    def _duration_in_range(cls, v: float) -> float:
        if not 0.5 <= v <= _MAX_TOTAL_SECONDS:
            raise ValueError("scene duration must be 0.5..60 seconds")
        return v

    @field_validator("transition")
    @classmethod
    def _transition_known(cls, v: str) -> str:
        if v not in ("cut", "crossfade", "fadeblack"):
            raise ValueError("transition must be cut, crossfade or fadeblack")
        return v


class CodeVideoTimeline(BaseModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30
    scenes: list[CodeVideoScene]
    audio: str | None = None

    @field_validator("scenes")
    @classmethod
    def _scenes_valid(cls, v: list[CodeVideoScene]) -> list[CodeVideoScene]:
        if not v:
            raise ValueError("at least one scene is required")
        if len(v) > _MAX_SCENES:
            raise ValueError(f"at most {_MAX_SCENES} scenes")
        total = sum(s.duration for s in v)
        if total > _MAX_TOTAL_SECONDS:
            raise ValueError(f"total duration {total}s exceeds {_MAX_TOTAL_SECONDS}s")
        return v


def _escape_drawtext(text: str) -> str:
    """Escape a string for ffmpeg drawtext (backslash, quote, colon, percent)."""
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("%", "\\%")
    )


def _resolve_font(explicit: str | None = None) -> str:
    candidates = [
        explicit,
        os.environ.get("HINAA_VIDEO_FONT"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for cand in candidates:
        if cand and Path(cand).exists():
            return cand
    try:
        out = subprocess.run(
            ["fc-match", "--format", "%{file}", "sans-serif:bold"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip() and Path(out.stdout.strip()).exists():
            return out.stdout.strip()
    except Exception:
        pass
    raise HinaaError(
        "CODE_VIDEO_NO_FONT",
        "No usable font found for video text rendering; set HINAA_VIDEO_FONT to a .ttf path.",
        500,
        True,
    )


def _is_color(value: str) -> bool:
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return True
    return value.lower() in {
        "black", "white", "red", "green", "blue", "yellow", "cyan",
        "magenta", "gray", "grey", "orange", "purple", "pink", "brown",
    }


def _probe(path: Path) -> dict[str, Any]:
    """Real ffprobe check: a real video stream, resolution and duration."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise HinaaError(
            "CODE_VIDEO_NO_FFPROBE",
            "ffprobe is missing; cannot verify the rendered video.",
            500,
            True,
        )
    out = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height",
         "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        raise HinaaError("CODE_VIDEO_BAD_OUTPUT", f"ffprobe failed: {out.stderr[-300:]}", 502, True)
    data = json.loads(out.stdout or "{}")
    streams = data.get("streams") or []
    if not streams:
        raise HinaaError("CODE_VIDEO_BAD_OUTPUT", "Rendered file has no video stream.", 502, True)
    return {
        "codec": streams[0].get("codec_name"),
        "width": streams[0].get("width"),
        "height": streams[0].get("height"),
        "duration": float(data.get("format", {}).get("duration") or 0),
        "file_size": path.stat().st_size,
    }


def _run(cmd: list[str], what: str) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise HinaaError(
            "CODE_VIDEO_RENDER_FAILED",
            f"ffmpeg {what} failed: {proc.stderr[-500:]}",
            502,
            True,
        )


class CodeVideoProvider(CreativeProvider):
    """Renders a brain-written timeline to a real MP4 with local ffmpeg."""

    def __init__(self, *, ffmpeg: str | None = None) -> None:
        self._ffmpeg = ffmpeg or shutil.which("ffmpeg") or "ffmpeg"

    @property
    def provider_id(self) -> str:
        return "code_video"

    def is_available(self) -> bool:
        return bool(shutil.which("ffmpeg"))

    def supported_operations(self) -> list[CreativeOperation]:
        return [CreativeOperation.TIMELINE_EXPORT, CreativeOperation.TEXT_TO_VIDEO]

    def render_timeline(self, timeline: CodeVideoTimeline) -> bytes:
        """Render the timeline synchronously; returns real MP4 bytes."""
        if not shutil.which(self._ffmpeg):
            raise HinaaError(
                "CODE_VIDEO_NO_FFMPEG",
                "ffmpeg is not installed on this machine, so code video rendering is unavailable.",
                500,
                True,
            )
        total = sum(s.duration for s in timeline.scenes)
        # xfade joins consume transition time: expected output is shorter.
        # Same clamp as _join_segments: at most 1 s, at most half of either
        # neighbouring scene.
        expected = total - sum(
            min(s.transition_duration, 1.0,
                0.5 * timeline.scenes[i - 1].duration, 0.5 * s.duration)
            if s.transition != "cut" else 0.0
            for i, s in enumerate(timeline.scenes[1:], start=1)
        )
        with tempfile.TemporaryDirectory(prefix="hinaa_code_video_") as tmp:
            tmp_path = Path(tmp)
            segments = [
                self._render_scene(i, scene, timeline, tmp_path)
                for i, scene in enumerate(timeline.scenes)
            ]
            out_path = tmp_path / "output.mp4"
            self._join_segments(segments, timeline, tmp_path, out_path, total)
            if timeline.audio:
                self._mix_audio(out_path, timeline, tmp_path, expected)
            probe = _probe(out_path)
            if probe["file_size"] < _MIN_MP4_BYTES:
                raise HinaaError("CODE_VIDEO_BAD_OUTPUT", "Rendered video is suspiciously small.", 502, True)
            if abs(probe["duration"] - expected) > 0.6:
                raise HinaaError(
                    "CODE_VIDEO_BAD_OUTPUT",
                    f"Rendered duration {probe['duration']:.2f}s does not match timeline {total:.2f}s.",
                    502,
                    True,
                )
            if probe["width"] != timeline.width or probe["height"] != timeline.height:
                raise HinaaError(
                    "CODE_VIDEO_BAD_OUTPUT",
                    f"Rendered {probe['width']}x{probe['height']} does not match timeline "
                    f"{timeline.width}x{timeline.height}.",
                    502,
                    True,
                )
            return out_path.read_bytes()

    def _render_scene(
        self, index: int, scene: CodeVideoScene, timeline: CodeVideoTimeline, tmp_path: Path
    ) -> Path:
        """Render one scene to its own segment MP4."""
        seg = tmp_path / f"scene_{index:02d}.mp4"
        filters: list[str] = []
        if _is_color(scene.background):
            color = scene.background[1:] if scene.background.startswith("#") else scene.background
            inputs = ["-f", "lavfi", "-i",
                      f"color=c={color}:s={timeline.width}x{timeline.height}:r={timeline.fps}:d={scene.duration}"]
            vf = "format=yuv420p"
        else:
            bg_path = Path(scene.background)
            if not bg_path.exists():
                raise HinaaError(
                    "CODE_VIDEO_BAD_BACKGROUND",
                    f"Scene {index} background image not found: {scene.background}",
                    400,
                    True,
                )
            inputs = ["-loop", "1", "-t", str(scene.duration), "-i", str(bg_path)]
            vf = (
                f"scale={timeline.width}:{timeline.height}:force_original_aspect_ratio=increase,"
                f"crop={timeline.width}:{timeline.height},"
                f"zoompan=z='min(zoom+0.0005,1.1)':d={int(scene.duration * timeline.fps)}:"
                f"s={timeline.width}x{timeline.height}:fps={timeline.fps},format=yuv420p"
            )
        for t in scene.texts:
            font = _resolve_font(t.font)
            end = t.end if t.end is not None else scene.duration
            vf += (
                f",drawtext=fontfile={font}:text='{_escape_drawtext(t.text)}':"
                f"fontsize={t.size}:fontcolor={t.color}:x={t.x}:y={t.y}:"
                f"enable='between(t,{t.start},{end})'"
            )
        cmd = [self._ffmpeg, "-y", *inputs, "-vf", vf,
               "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-t", str(scene.duration), str(seg)]
        _run(cmd, f"scene {index}")
        return seg

    def _join_segments(
        self, segments: list[Path], timeline: CodeVideoTimeline,
        tmp_path: Path, out_path: Path, total: float,
    ) -> None:
        """Join scene segments with cuts or crossfades."""
        if len(segments) == 1:
            shutil.copyfile(segments[0], out_path)
            return
        transitions = [s.transition for s in timeline.scenes[1:]]
        if all(t == "cut" for t in transitions):
            concat_list = tmp_path / "concat.txt"
            concat_list.write_text(
                "".join(f"file '{s}'\n" for s in segments)
            )
            _run([self._ffmpeg, "-y", "-f", "concat", "-safe", "0",
                  "-i", str(concat_list), "-c", "copy", str(out_path)], "concat")
            return
        # xfade chain: each join eats transition_duration from the running total.
        inputs: list[str] = []
        for s in segments:
            inputs += ["-i", str(s)]
        filter_parts: list[str] = []
        offset = timeline.scenes[0].duration
        prev = "[0:v]"
        for i, scene in enumerate(timeline.scenes[1:], start=1):
            trans = scene.transition
            # Never eat more than half of either neighbouring scene.
            dur = min(scene.transition_duration, 1.0,
                      0.5 * timeline.scenes[i - 1].duration, 0.5 * scene.duration)
            xfade_name = "fade" if trans == "crossfade" else "fadeblack" if trans == "fadeblack" else "fade"
            out_label = f"[x{i}]" if i < len(segments) - 1 else "[vout]"
            filter_parts.append(
                f"{prev}[{i}:v]xfade=transition={xfade_name}:duration={dur}:offset={offset - dur:.3f}{out_label}"
            )
            prev = out_label
            offset += scene.duration - dur
        cmd = [self._ffmpeg, "-y", *inputs,
               "-filter_complex", ";".join(filter_parts),
               "-map", "[vout]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-t", str(total), str(out_path)]
        _run(cmd, "xfade join")

    def _mix_audio(self, video_path: Path, timeline: CodeVideoTimeline, tmp_path: Path, total: float) -> None:
        audio_path = Path(timeline.audio) if timeline.audio else None
        if audio_path is None or not audio_path.exists():
            raise HinaaError(
                "CODE_VIDEO_BAD_AUDIO",
                f"Audio file not found: {timeline.audio}",
                400,
                True,
            )
        mixed = tmp_path / "mixed.mp4"
        _run([self._ffmpeg, "-y", "-i", str(video_path), "-i", str(audio_path),
              "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
              "-t", str(total), str(mixed)], "audio mix")
        shutil.copyfile(mixed, video_path)

    async def execute_job(self, job: CreativeJobRecord) -> bytes:
        raw = (job.spec.timeline_json or {})
        if not raw:
            raise HinaaError(
                "VIDEO_TIMELINE_REQUIRED",
                "To make a video by code, the model must write a timeline "
                "(scenes with text, timing and transitions). No timeline was provided.",
                400,
                True,
            )
        try:
            timeline = CodeVideoTimeline.model_validate(raw)
        except Exception as exc:
            raise HinaaError(
                "VIDEO_TIMELINE_INVALID",
                f"The video timeline is invalid: {exc}",
                400,
                True,
            ) from exc
        # Audio comes from the timeline itself ("audio": "/path/to/song.mp3").
        return await asyncio.to_thread(self.render_timeline, timeline)

    async def cancel_job(self, provider_job_id: str) -> bool:
        return False


code_video_provider = CodeVideoProvider()
