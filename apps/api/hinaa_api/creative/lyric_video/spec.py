"""Lyric-video spec: validation, timing resolution and scene assignment."""
# ruff: noqa: E501, S603, S607

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCENE_PRESETS = ("dreamy-sky", "hills-day", "starry-night-flags", "snow-window", "love-burst")
ASPECTS: dict[str, tuple[int, int]] = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
DEFAULT_LINE_SECONDS = 3.0
MAX_LINES = 60
MAX_DURATION = 300.0
AUDIO_SUFFIXES = {".mp3", ".wav"}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

_SCENE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "starry-night-flags": ("night", "star", "moon", "dark", "dream", "raat", "taara", "jun", "pray", "flag"),
    "snow-window": ("snow", "cold", "winter", "rain", "chiso", "himal", "window", "alone", "miss", "tear"),
    "love-burst": ("love", "maya", "heart", "pyar", "kiss", "promise", "forever", "mann", "man ", "rakhana"),
    "hills-day": ("hill", "mountain", "pahad", "daada", "dada", "sun", "day", "field", "dance", "nachi", "village"),
    "dreamy-sky": ("sky", "cloud", "fly", "asha", "smile", "hasi", "yaad", "wish", "wait"),
}


class LyricLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=200)
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, gt=0)
    scene: str | None = None

    @field_validator("text")
    @classmethod
    def _clean_text(cls, v: str) -> str:
        v = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", v).strip()
        if not v:
            raise ValueError("lyric text must not be blank")
        return v

    @field_validator("scene")
    @classmethod
    def _known_scene(cls, v: str | None) -> str | None:
        if v is not None and v not in SCENE_PRESETS:
            raise ValueError(f"unknown scene '{v}'; choose one of {', '.join(SCENE_PRESETS)}")
        return v

    @model_validator(mode="after")
    def _order(self) -> LyricLine:
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("line end must be greater than start")
        return self


class LyricSticker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=60)
    at: float = Field(ge=0)


class Palette(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = "#ffffff"
    accent: str = "#ff7ac8"
    accent2: str = "#a46bff"
    outline: str = "#5b2a86"

    @field_validator("*")
    @classmethod
    def _hex(cls, v: str) -> str:
        if not _HEX.match(v):
            raise ValueError("palette colours must be #rrggbb")
        return v


class LyricVideoSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="Lyric Video", max_length=80)
    lines: list[LyricLine] = Field(min_length=1, max_length=MAX_LINES)
    audio_path: str | None = None
    character_image: str | None = None
    palette: Palette = Field(default_factory=Palette)
    stickers: list[LyricSticker] = Field(default_factory=list, max_length=20)
    aspect: Literal["9:16", "16:9", "1:1"] = "9:16"
    fps: Literal[30] = 30
    draft: bool = False

    @field_validator("audio_path")
    @classmethod
    def _audio_ok(cls, v: str | None) -> str | None:
        if v is None:
            return v
        p = Path(v)
        if p.suffix.lower() not in AUDIO_SUFFIXES:
            raise ValueError("audio_path must be an .mp3 or .wav file")
        if not p.is_file():
            raise ValueError("audio_path does not exist")
        return v

    @field_validator("character_image")
    @classmethod
    def _image_ok(cls, v: str | None) -> str | None:
        if v is None:
            return v
        p = Path(v)
        if p.suffix.lower() != ".png":
            raise ValueError("character_image must be a .png file")
        if not p.is_file():
            raise ValueError("character_image does not exist")
        if p.stat().st_size > 15 * 1024 * 1024:
            raise ValueError("character_image is larger than 15 MB")
        return v

    @property
    def size(self) -> tuple[int, int]:
        """Output pixel size."""
        w, h = ASPECTS[self.aspect]
        return (w // 2, h // 2) if self.draft else (w, h)


def probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, timeout=30, check=False,
    )
    try:
        return float(out.stdout.strip())
    except ValueError as exc:
        raise ValueError("could not read audio duration (is the file valid?)") from exc


class ResolvedLine(BaseModel):
    text: str
    start: float
    end: float
    scene: str


def pick_scene(text: str, index: int, previous: str | None) -> str:
    """Keyword match first, else rotate through presets; never repeat the previous scene."""
    low = f" {text.lower()} "
    for scene, words in _SCENE_KEYWORDS.items():
        if scene != previous and any(w in low for w in words):
            return scene
    scene = SCENE_PRESETS[index % len(SCENE_PRESETS)]
    if scene == previous:
        scene = SCENE_PRESETS[(index + 1) % len(SCENE_PRESETS)]
    return scene


def resolve_timeline(spec: LyricVideoSpec, audio_duration: float | None = None) -> tuple[list[ResolvedLine], float]:
    """Return lines with concrete timings/scenes plus the total video duration."""
    lines = spec.lines
    n = len(lines)
    explicit = any(ln.start is not None or ln.end is not None for ln in lines)
    if not explicit:
        total = audio_duration if audio_duration else DEFAULT_LINE_SECONDS * n
        step = total / n
        bounds = [(i * step, (i + 1) * step) for i in range(n)]
    else:
        bounds = []
        prev_end = 0.0
        for i, line in enumerate(lines):
            start = line.start if line.start is not None else prev_end
            if line.end is not None:
                end = line.end
            else:
                nxt = next((ln.start for ln in lines[i + 1:] if ln.start is not None), None)
                end = nxt if nxt is not None and nxt > start else start + DEFAULT_LINE_SECONDS
            if end <= start:
                raise ValueError(f"line {i + 1}: resolved end ({end:.2f}s) is not after start ({start:.2f}s)")
            bounds.append((start, end))
            prev_end = end
        total = audio_duration if audio_duration else max(e for _, e in bounds)
    if total > MAX_DURATION:
        raise ValueError(f"video would be {total:.0f}s; maximum is {MAX_DURATION:.0f}s")
    resolved: list[ResolvedLine] = []
    prev_scene: str | None = None
    for i, (line, (s, e)) in enumerate(zip(lines, bounds, strict=True)):
        scene = line.scene or pick_scene(line.text, i, prev_scene)
        resolved.append(ResolvedLine(text=line.text, start=round(s, 3), end=round(min(e, total), 3), scene=scene))
        prev_scene = scene
    resolved = [r for r in resolved if r.start < total]
    if not resolved:
        raise ValueError("no lyric line starts before the end of the audio")
    return resolved, round(total, 3)
