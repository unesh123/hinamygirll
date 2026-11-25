"""Video by code — brain-written JSON timeline rendered by local FFmpeg + ffprobe QC.

Renders scenes (solid colors or workspace/data-confined images), timed drawtext
typography, transitions (cut, crossfade, fadeblack), and optional workspace/data
audio with EBU R128 loudness normalization, verified strictly via ffprobe.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ...errors import HinaaError
from ...runtime_paths import project_root
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
    normalize_audio: bool = True

    @field_validator("width", "height")
    @classmethod
    def _dim_in_range(cls, v: int) -> int:
        if not 64 <= v <= 3840:
            raise ValueError("width/height must be 64..3840")
        return v

    @field_validator("fps")
    @classmethod
    def _fps_in_range(cls, v: int) -> int:
        if not 1 <= v <= 60:
            raise ValueError("fps must be 1..60")
        return v

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
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("%", "\\%")
    )


def _escape_ffmpeg_path(path_str: str) -> str:
    """Escape path separators and Windows drive colons inside FFmpeg filter strings."""
    posix = Path(path_str).as_posix()
    return posix.replace(":", "\\:")


def _allowed_media_roots() -> tuple[Path, ...]:
    root = Path(os.path.realpath(str(project_root())))
    roots = [
        root,
        Path(os.path.realpath(os.path.abspath(tempfile.gettempdir()))),
    ]
    ultra = Path(os.path.realpath(os.path.expanduser("~/hinaa-ultra")))
    if ultra.exists():
        roots.append(ultra)
    return tuple(roots)


def _resolve_confined_media_path(raw: str, *, code: str, label: str) -> Path:
    candidate = Path(os.path.realpath(os.path.abspath(raw)))
    allowed = _allowed_media_roots()
    if not any(candidate == r or r in candidate.parents for r in allowed):
        raise HinaaError(
            code,
            f"{label} path must stay inside the workspace, data, or temp directory: {raw}",
            403,
            False,
        )
    if not candidate.exists() or not candidate.is_file():
        raise HinaaError(code, f"{label} file not found: {raw}", 400, True)
    return candidate


def _resolve_font(explicit: str | None = None) -> str:
    candidates: list[str | None] = []
    if explicit:
        # Allow system Fonts directory or confined workspace/data font paths
        win_fonts = Path(os.path.realpath("C:/Windows/Fonts"))
        cand_real = Path(os.path.realpath(os.path.abspath(explicit)))
        if win_fonts in cand_real.parents or any(cand_real == r or r in cand_real.parents for r in _allowed_media_roots()):
            candidates.append(str(cand_real))
    candidates.extend([
        os.environ.get("HINAA_VIDEO_FONT"),
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
    ])
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
    import json

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise HinaaError(
            "CODE_VIDEO_NO_FFPROBE",
            "ffprobe is missing; cannot verify the rendered video.",
            500,
            True,
        )
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        raise HinaaError("CODE_VIDEO_BAD_OUTPUT", f"ffprobe failed: {out.stderr[-300:]}", 502, True)
    data = json.loads(out.stdout or "{}")
    streams = data.get("streams") or []
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not v_stream:
        raise HinaaError("CODE_VIDEO_BAD_OUTPUT", "Rendered file has no video stream.", 502, True)
    raw_bytes = path.read_bytes()
    return {
        "codec": v_stream.get("codec_name"),
        "width": v_stream.get("width"),
        "height": v_stream.get("height"),
        "duration": float(data.get("format", {}).get("duration") or 0),
        "audio_codec": a_stream.get("codec_name") if a_stream else None,
        "audio_channels": a_stream.get("channels") if a_stream else 0,
        "file_size": len(raw_bytes),
        "checksum_sha256": hashlib.sha256(raw_bytes).hexdigest(),
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
        self.last_probe: dict[str, Any] | None = None

    @property
    def provider_id(self) -> str:
        return "code_video"

    def is_available(self) -> bool:
        return bool(shutil.which(self._ffmpeg))

    def supported_operations(self) -> list[CreativeOperation]:
        return [CreativeOperation.TIMELINE_EXPORT, CreativeOperation.TEXT_TO_VIDEO]

    def render_timeline(self, timeline: CodeVideoTimeline) -> bytes:
        if not shutil.which(self._ffmpeg):
            raise HinaaError(
                "CODE_VIDEO_NO_FFMPEG",
                "ffmpeg is not installed on this machine, so code video rendering is unavailable.",
                500,
                True,
            )
        total = sum(s.duration for s in timeline.scenes)
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
            self.last_probe = probe
            if probe["file_size"] < _MIN_MP4_BYTES:
                raise HinaaError("CODE_VIDEO_BAD_OUTPUT", "Rendered video is suspiciously small.", 502, True)
            if abs(probe["duration"] - expected) > 0.6:
                raise HinaaError(
                    "CODE_VIDEO_BAD_OUTPUT",
                    f"Rendered duration {probe['duration']:.2f}s does not match timeline {expected:.2f}s.",
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
        seg = tmp_path / f"scene_{index:02d}.mp4"
        if _is_color(scene.background):
            color = scene.background[1:] if scene.background.startswith("#") else scene.background
            inputs = ["-f", "lavfi", "-i",
                      f"color=c={color}:s={timeline.width}x{timeline.height}:r={timeline.fps}:d={scene.duration}"]
            vf = "format=yuv420p"
        else:
            bg_path = _resolve_confined_media_path(
                scene.background, code="CODE_VIDEO_BAD_BACKGROUND", label=f"Scene {index} background image"
            )
            inputs = ["-loop", "1", "-t", str(scene.duration), "-i", str(bg_path)]
            vf = (
                f"scale={timeline.width}:{timeline.height}:force_original_aspect_ratio=increase,"
                f"crop={timeline.width}:{timeline.height},"
                f"zoompan=z='min(zoom+0.0005,1.1)':d={int(scene.duration * timeline.fps)}:"
                f"s={timeline.width}x{timeline.height}:fps={timeline.fps},format=yuv420p"
            )
        for t in scene.texts:
            font = _escape_ffmpeg_path(_resolve_font(t.font))
            end = t.end if t.end is not None else scene.duration
            vf += (
                f",drawtext=fontfile='{font}':text='{_escape_drawtext(t.text)}':"
                f"fontsize={t.size}:fontcolor={t.color}:x={t.x}:y={t.y}:"
                f"enable='between(t,{t.start},{end})'"
            )
        cmd = [self._ffmpeg, "-y", *inputs, "-vf", vf,
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
               "-t", str(scene.duration), str(seg)]
        _run(cmd, f"scene {index}")
        return seg

    def _join_segments(
        self, segments: list[Path], timeline: CodeVideoTimeline,
        tmp_path: Path, out_path: Path, total: float,
    ) -> None:
        if len(segments) == 1:
            shutil.copyfile(segments[0], out_path)
            return
        transitions = [s.transition for s in timeline.scenes[1:]]
        if all(t == "cut" for t in transitions):
            concat_list = tmp_path / "concat.txt"
            concat_list.write_text("".join(f"file '{s.as_posix()}'\n" for s in segments), encoding="utf-8")
            _run([self._ffmpeg, "-y", "-f", "concat", "-safe", "0",
                  "-i", str(concat_list), "-c", "copy", str(out_path)], "concat")
            return
        inputs: list[str] = []
        for s in segments:
            inputs += ["-i", str(s)]
        filter_parts: list[str] = []
        offset = timeline.scenes[0].duration
        prev = "[0:v]"
        for i, scene in enumerate(timeline.scenes[1:], start=1):
            trans = scene.transition
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
               "-map", "[vout]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
               "-t", str(total), str(out_path)]
        _run(cmd, "xfade join")

    def _mix_audio(self, video_path: Path, timeline: CodeVideoTimeline, tmp_path: Path, total: float) -> None:
        audio_path = _resolve_confined_media_path(
            timeline.audio or "", code="CODE_VIDEO_BAD_AUDIO", label="Audio"
        )
        mixed = tmp_path / "mixed.mp4"
        cmd = [
            self._ffmpeg, "-y", "-i", str(video_path), "-i", str(audio_path),
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        ]
        if timeline.normalize_audio:
            cmd.extend(["-filter:a", "loudnorm=I=-14:TP=-1.0:LRA=11"])
        cmd.extend(["-movflags", "+faststart", "-t", str(total), str(mixed)])
        _run(cmd, "audio mix")
        shutil.copyfile(mixed, video_path)

    async def execute_job(self, job: CreativeJobRecord) -> bytes:
        raw = job.spec.timeline_json or {}
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
        data = await asyncio.to_thread(self.render_timeline, timeline)
        if self.last_probe:
            job.telemetry["code_video_probe"] = dict(self.last_probe)
        return data

    async def cancel_job(self, provider_job_id: str) -> bool:
        return False


code_video_provider = CodeVideoProvider()
