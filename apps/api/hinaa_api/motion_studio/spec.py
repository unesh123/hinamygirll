"""Bounded scene graph understood by HINA's chat renderer and offline preview."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MotionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Keyframe(MotionModel):
    time: float = Field(ge=0, le=30)
    x: float = Field(0, ge=-2, le=2, description="Offset as a fraction of canvas width.")
    y: float = Field(0, ge=-2, le=2, description="Offset as a fraction of canvas height.")
    scale: float = Field(1, ge=0.05, le=8)
    rotation: float = Field(0, ge=-720, le=720)
    opacity: float = Field(1, ge=0, le=1)
    ease: Literal["linear", "cubic", "expo", "spring"] = "cubic"


class MotionLayer(MotionModel):
    kind: Literal["text", "image", "video", "rect", "ring", "line"] = "text"
    text: str = Field("", max_length=500)
    path: str | None = Field(None, max_length=500)
    start: float = Field(0, ge=0, le=30)
    end: float | None = Field(None, gt=0, le=30)
    x: float = Field(0.5, ge=0, le=1)
    y: float = Field(0.5, ge=0, le=1)
    size: float = Field(
        0.16, ge=0.006, le=2, description="Font size or shape width / canvas width."
    )
    height: float = Field(0.1, ge=0.001, le=2)
    max_width: float = Field(0.84, gt=0, le=1)
    color: str = Field("#f6f1e7", pattern=r"^#[0-9a-fA-F]{6}$")
    stroke: str = Field("#f6f1e7", pattern=r"^#[0-9a-fA-F]{6}$")
    outline: bool = False
    align: Literal["left", "center", "right"] = "center"
    font: Literal["sans", "serif", "mono"] = "sans"
    weight: Literal[400, 600, 700, 900] = 900
    tracking: float = Field(0, ge=-0.08, le=0.35, description="Letter spacing / font size.")
    motion: Literal[
        "none",
        "mask_rise",
        "word_reveal",
        "letter_stagger",
        "tracking",
        "perspective",
        "slash",
        "blur_rise",
        "typewriter",
        "scale_pop",
    ] = "mask_rise"
    entrance: float = Field(0.55, ge=0.05, le=4)
    stagger: float = Field(0.045, ge=0, le=0.5)
    unit_times: list[float] = Field(default_factory=list, max_length=200)
    depth: float = Field(0, ge=-2, le=2)
    opacity: float = Field(1, ge=0, le=1)
    blend: Literal["source-over", "screen", "multiply", "overlay"] = "source-over"
    motion_blur: bool = False
    fit: Literal["cover", "contain"] = "cover"
    media_start: float = Field(0, ge=0, le=86400)
    playback_rate: float = Field(1, ge=0.25, le=4)
    keyframes: list[Keyframe] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def valid_content(self):
        if self.kind == "text" and not self.text.strip():
            raise ValueError("text layers require nonblank text")
        if self.kind in ("image", "video") and not self.path:
            raise ValueError("image/video layers require a local path")
        if self.kind not in ("image", "video") and self.path:
            raise ValueError("only image/video layers accept a path")
        if self.end is not None and self.end <= self.start:
            raise ValueError("layer end must follow start")
        if self.unit_times != sorted(self.unit_times) or any(
            t < 0 or t > 30 for t in self.unit_times
        ):
            raise ValueError("unit_times must be ascending, finite seconds in 0..30")
        times = [k.time for k in self.keyframes]
        if times != sorted(set(times)):
            raise ValueError("keyframe times must be unique and ascending")
        return self


class MotionScene(MotionModel):
    duration: float = Field(ge=0.3, le=30)
    background: str = Field("#0c1019", pattern=r"^#[0-9a-fA-F]{6}$")
    accent: str = Field("#75d9ff", pattern=r"^#[0-9a-fA-F]{6}$")
    transition: Literal["cut", "crossfade", "wipe", "diagonal", "whip", "iris"] = "cut"
    transition_duration: float = Field(0.22, ge=0.05, le=1)
    camera: Literal["static", "dolly", "pan_left", "pan_right", "orbit", "crash_zoom"] = "static"
    camera_amount: float = Field(0.07, ge=0, le=0.4)
    atmosphere: Literal["none", "dust", "embers"] = "none"
    layers: list[MotionLayer] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def check_timing(self):
        for layer in self.layers:
            if layer.start >= self.duration or (
                layer.end is not None and layer.end > self.duration
            ):
                raise ValueError("layer timing must fit inside its scene")
            span = (layer.end or self.duration) - layer.start
            if any(k.time > span for k in layer.keyframes) or any(
                t >= span for t in layer.unit_times
            ):
                raise ValueError("keyframes/unit_times must fit inside the visible layer interval")
        return self


class MotionComposition(MotionModel):
    version: Literal[1] = 1
    scenes: list[MotionScene] = Field(min_length=1, max_length=20)
    accents: list[float] = Field(default_factory=list, max_length=500)
    safe_margin: float = Field(0.075, ge=0, le=0.25)

    @property
    def duration(self) -> float:
        return round(sum(s.duration for s in self.scenes), 6)

    @model_validator(mode="after")
    def check_duration(self):
        if self.duration > 30:
            raise ValueError("composition duration must be at most 30 seconds")
        if self.accents != sorted(set(self.accents)) or any(
            t < 0 or t >= self.duration for t in self.accents
        ):
            raise ValueError("accents must be unique ascending seconds inside the composition")
        for scene in self.scenes:
            for layer in scene.layers:
                if layer.kind == "text" and not (self.safe_margin < layer.x < 1 - self.safe_margin):
                    raise ValueError("text anchors must be inside the horizontal safe margins")
        return self
