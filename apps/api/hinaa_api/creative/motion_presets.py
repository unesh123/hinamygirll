"""Offline procedural motion, anime impact, camera, and grade presets (Pillow + NumPy).

No external video API calls; operates deterministically on frames or single images.
"""
from __future__ import annotations

import math
from typing import Literal, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MotionPresetName = Literal[
    "katana_slash",
    "aura_farming",
    "vhs",
    "glitch",
    "dolly_in",
    "orbit",
    "teal_orange",
    "hyper_neon",
]

PRESET_NAMES: tuple[MotionPresetName, ...] = (
    "katana_slash",
    "aura_farming",
    "vhs",
    "glitch",
    "dolly_in",
    "orbit",
    "teal_orange",
    "hyper_neon",
)


def _to_rgb_array(image: Image.Image) -> np.ndarray:
    if image.mode != "RGB":
        image = image.convert("RGB")
    return np.asarray(image, dtype=np.float32)


def _clamp_u8(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")


def _crop_resize_box(
    image: Image.Image,
    zoom: float,
    shift_x: float = 0.0,
    shift_y: float = 0.0,
) -> Image.Image:
    w, h = image.size
    z = max(1.0, float(zoom))
    cw = max(2.0, w / z)
    ch = max(2.0, h / z)
    cx = w * 0.5 + shift_x * (w - cw) * 0.45
    cy = h * 0.5 + shift_y * (h - ch) * 0.45
    x0 = max(0.0, min(w - cw, cx - cw * 0.5))
    y0 = max(0.0, min(h - ch, cy - ch * 0.5))
    return image.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), Image.Resampling.BICUBIC)


def apply_preset(
    image: Image.Image,
    preset: str,
    *,
    progress: float = 0.5,
    intensity: float = 1.0,
) -> Image.Image:
    """Apply a deterministic procedural effect preset to one PIL Image."""
    name = str(preset or "").strip().lower()
    if name not in PRESET_NAMES:
        raise ValueError(f"Unsupported motion preset {preset!r}. Choose one of: {', '.join(PRESET_NAMES)}")
    t = max(0.0, min(1.0, float(progress)))
    amp = max(0.0, min(2.0, float(intensity)))
    base = image.convert("RGB")
    w, h = base.size

    if name == "dolly_in":
        ease = t * t * (3.0 - 2.0 * t)
        zoom = 1.0 + 0.24 * amp * ease
        return _crop_resize_box(base, zoom=zoom)

    if name == "orbit":
        angle = t * math.tau
        zoom = 1.0 + 0.14 * amp
        return _crop_resize_box(base, zoom=zoom, shift_x=math.sin(angle), shift_y=math.cos(angle) * 0.65)

    if name == "katana_slash":
        arr = _to_rgb_array(base)
        # Mild lateral chromatic smear at peak slash timing
        shift = max(1, int(round(6 * amp * math.sin(max(0.08, t) * math.pi))))
        smeared = arr.copy()
        if w > shift * 2:
            smeared[:, shift:, 0] = np.maximum(smeared[:, shift:, 0], arr[:, :-shift, 0] * 0.92)
            smeared[:, :-shift, 2] = np.maximum(smeared[:, :-shift, 2], arr[:, shift:, 2] * 0.95)
        out = _clamp_u8(smeared)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        slash_x0 = int(w * (0.08 + 0.12 * t))
        slash_y0 = int(h * 0.85)
        slash_x1 = int(w * (0.92 - 0.08 * t))
        slash_y1 = int(h * 0.14)
        outer_w = max(4, int(min(w, h) * 0.045 * amp))
        core_w = max(2, int(min(w, h) * 0.014 * amp))
        draw.line((slash_x0, slash_y0, slash_x1, slash_y1), fill=(139, 92, 246, 150), width=outer_w)
        draw.line((slash_x0, slash_y0, slash_x1, slash_y1), fill=(224, 248, 255, 245), width=core_w)
        glow = overlay.filter(ImageFilter.GaussianBlur(radius=max(1.0, outer_w * 0.45)))
        merged = Image.alpha_composite(out.convert("RGBA"), glow)
        merged = Image.alpha_composite(merged, overlay)
        return merged.convert("RGB")

    if name == "aura_farming":
        glow = base.filter(ImageFilter.GaussianBlur(radius=max(2.0, min(w, h) * 0.03)))
        arr = _to_rgb_array(base)
        g_arr = _to_rgb_array(glow)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        dx = (xx / max(1, w) - 0.5) * 2.0
        dy = (yy / max(1, h) - 0.55) * 2.0
        dist = np.sqrt(dx * dx + dy * dy)
        pulse = 0.7 + 0.3 * math.sin(t * math.tau)
        ring = np.exp(-((dist - (0.58 + 0.12 * math.sin(t * math.pi))) ** 2) / 0.09) * amp * pulse
        aura = arr * 0.82 + g_arr * 0.25
        aura[:, :, 0] += ring * 78.0
        aura[:, :, 1] += ring * 44.0
        aura[:, :, 2] += ring * 135.0
        return _clamp_u8(aura)

    if name == "vhs":
        arr = _to_rgb_array(base)
        offset = max(1, int(round(3 * amp)))
        out = arr.copy()
        if w > offset * 2:
            out[:, offset:, 0] = arr[:, :-offset, 0]
            out[:, :-offset, 2] = arr[:, offset:, 2]
        scan_phase = int(round(t * 16))
        rows = np.arange(h)[:, None, None]
        scan_mask = np.where(((rows + scan_phase) % 4) == 0, 0.78, 1.04)
        out *= scan_mask
        # Deterministic pseudo-grain per progress step
        rng = np.random.default_rng(int(round(t * 1000)) + 17)
        noise = rng.normal(0.0, 6.5 * amp, size=(h, w, 1)).astype(np.float32)
        return _clamp_u8(out + noise)

    if name == "glitch":
        arr = _to_rgb_array(base)
        out = arr.copy()
        strips = max(3, int(round(5 * amp)))
        for idx in range(strips):
            y0 = int(((idx * 0.19 + t * 0.37) % 0.85) * h)
            sh = max(2, min(h - y0, max(3, h // 18)))
            dx = int(round((1 if idx % 2 == 0 else -1) * w * 0.045 * amp))
            out[y0 : y0 + sh] = np.roll(out[y0 : y0 + sh], shift=dx, axis=1)
        if w > 4:
            out[:, 2:, 0] = np.maximum(out[:, 2:, 0], out[:, :-2, 0] * 0.9)
        return _clamp_u8(out)

    if name == "teal_orange":
        arr = _to_rgb_array(base)
        luma = (arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114) / 255.0
        shadows = (1.0 - luma) ** 1.4
        highlights = luma ** 1.3
        k = 36.0 * amp
        out = arr.copy()
        out[:, :, 0] += highlights * k - shadows * (k * 0.65)
        out[:, :, 1] += shadows * (k * 0.35) + highlights * (k * 0.15)
        out[:, :, 2] += shadows * k - highlights * (k * 0.55)
        return _clamp_u8(out)

    # hyper_neon
    arr = _to_rgb_array(base)
    luma = (arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114) / 255.0
    hi = np.clip((luma - 0.35) / 0.65, 0.0, 1.0)
    out = arr * (0.9 + 0.25 * amp)
    out[:, :, 0] += hi * 42.0 * amp
    out[:, :, 1] += hi * 18.0 * amp
    out[:, :, 2] += hi * 64.0 * amp
    return _clamp_u8(out)


def apply_preset_sequence(
    frames: Sequence[Image.Image],
    preset: str,
    *,
    intensity: float = 1.0,
) -> list[Image.Image]:
    """Apply a preset smoothly across a frame sequence using normalized frame progress."""
    count = len(frames)
    if count == 0:
        return []
    if count == 1:
        return [apply_preset(frames[0], preset, progress=0.5, intensity=intensity)]
    return [
        apply_preset(frame, preset, progress=i / (count - 1), intensity=intensity)
        for i, frame in enumerate(frames)
    ]


__all__ = [
    "MotionPresetName",
    "PRESET_NAMES",
    "apply_preset",
    "apply_preset_sequence",
]
