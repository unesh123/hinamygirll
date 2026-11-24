"""
HINAA OS — Frontier Cinematic Kinetic Reel & Generative Motion Studio.
Implements screen-filling monumental typography, continuous 3D camera choreography,
layered liquid metallic chrome sphere rendering, orbital rings, and deterministic MP4 compilation.
"""

from __future__ import annotations

import io
import math
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


# Easing functions for cinematic choreography
def ease_out_expo(t: float) -> float:
    return 1.0 if t >= 1.0 else 1.0 - math.pow(2.0, -10.0 * t)


def ease_in_out_cubic(t: float) -> float:
    return 4.0 * t * t * t if t < 0.5 else 1.0 - math.pow(-2.0 * t + 2.0, 3.0) / 2.0


def ease_out_back(t: float, s: float = 1.70158) -> float:
    t = min(1.0, max(0.0, t))
    t -= 1.0
    return t * t * ((s + 1.0) * t + s) + 1.0


@dataclass
class KineticSceneSpec:
    headline: str
    subhead: str = ""
    kicker: str = "HINA / KINETIC"
    duration: float = 3.5
    accent_color: str = "#00f0ff"
    theme: str = "chrome_liquid"  # "chrome_liquid" | "deep_cyber" | "obsidian_gold"
    camera_motion: str = "dolly_in"  # "dolly_in" | "orbit_pan" | "zoom_burst" | "low_sweep"
    transition: str = "chromatic_whip"  # "chromatic_whip" | "glitch_snap" | "optical_fade"


@dataclass
class KineticReelSpec:
    title: str
    scenes: List[KineticSceneSpec]
    width: int = 1080
    height: int = 1920
    fps: int = 30
    audio_path: Optional[str] = None


class KineticMotionRenderer:
    """Renders high-fidelity kinetic typography and 3D procedural metallic visuals."""

    def __init__(self, font_family: Optional[str] = None):
        self._font_cache: Dict[int, ImageFont.FreeTypeFont] = {}
        self._font_family = font_family

    def _get_font(self, size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if size in self._font_cache:
            return self._font_cache[size]

        font_candidates = [
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc",
        ]
        font = None
        for fc in font_candidates:
            if Path(fc).exists():
                try:
                    font = ImageFont.truetype(fc, size)
                    break
                except Exception:
                    continue

        if font is None:
            font = ImageFont.load_default(size=size)

        self._font_cache[size] = font
        return font

    def _render_chrome_sphere(
        self,
        width: int,
        height: int,
        cx: float,
        cy: float,
        radius: float,
        time_sec: float,
        accent_rgb: Tuple[int, int, int],
    ) -> Image.Image:
        """Procedurally renders a raymarched liquid metallic chrome sphere with specular sheen and orbital rings."""
        # Create a bounding box image for the sphere and rings to optimize rendering
        pad = int(radius * 1.8)
        box_w = min(width, int(radius * 3.6))
        box_h = min(height, int(radius * 3.6))
        
        # Center in box
        local_cx = box_w / 2.0
        local_cy = box_h / 2.0

        y_coords, x_coords = np.ogrid[:box_h, :box_w]
        dx = (x_coords - local_cx) / radius
        dy = (y_coords - local_cy) / radius
        r2 = dx * dx + dy * dy

        # Sphere mask
        sphere_mask = r2 <= 1.0
        dz = np.zeros_like(r2)
        dz[sphere_mask] = np.sqrt(np.maximum(0.0, 1.0 - r2[sphere_mask]))

        # Normal vectors
        nx = dx * sphere_mask
        ny = dy * sphere_mask
        nz = dz

        # Liquid surface perturbation
        ripple = 0.08 * np.sin(5.0 * nx + 4.0 * ny + time_sec * 3.5) * sphere_mask
        nx += ripple
        ny += ripple

        # Normalization
        norm = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-6
        nx /= norm
        ny /= norm
        nz /= norm

        # Key light (upper-right front)
        lx, ly, lz = 0.577, -0.577, 0.577
        diffuse = np.maximum(0.0, nx * lx + ny * ly + nz * lz)

        # Chrome metallic reflection (Environment map simulation)
        # Reflection vector r = 2(n.v)n - v, where v = (0,0,1)
        rx = 2.0 * nz * nx
        ry = 2.0 * nz * ny
        rz = 2.0 * nz * nz - 1.0

        # Horizon band reflection (classic chrome horizon line with sky and ground contrast)
        env_horizon = 0.5 + 0.5 * np.sin(ry * 4.0 + time_sec * 0.8)
        env_spec = np.power(np.maximum(0.0, rz), 24.0)

        # Fresnel effect
        fresnel = np.power(1.0 - nz, 3.0)

        # RGB assembly
        r_chan = np.zeros((box_h, box_w), dtype=np.float32)
        g_chan = np.zeros((box_h, box_w), dtype=np.float32)
        b_chan = np.zeros((box_h, box_w), dtype=np.float32)

        # Base chrome tone
        chrome_base = 0.25 + 0.65 * env_horizon + 0.8 * env_spec
        r_chan[sphere_mask] = chrome_base[sphere_mask] * (accent_rgb[0] / 255.0 * 0.6 + 0.4) + fresnel[sphere_mask] * 0.8
        g_chan[sphere_mask] = chrome_base[sphere_mask] * (accent_rgb[1] / 255.0 * 0.6 + 0.4) + fresnel[sphere_mask] * 0.85
        b_chan[sphere_mask] = chrome_base[sphere_mask] * (accent_rgb[2] / 255.0 * 0.6 + 0.4) + fresnel[sphere_mask] * 0.95

        # Specular glint
        spec_glint = np.power(np.maximum(0.0, nx * 0.5 - ny * 0.6 + nz * 0.6), 40.0) * sphere_mask
        r_chan += spec_glint * 1.5
        g_chan += spec_glint * 1.5
        b_chan += spec_glint * 1.5

        # Alpha mask for sphere
        alpha_chan = np.zeros((box_h, box_w), dtype=np.float32)
        alpha_chan[sphere_mask] = 1.0
        # Smooth edge
        edge = np.maximum(0.0, 1.0 - np.abs(r2 - 1.0) * 15.0) * (r2 > 0.85) * (r2 <= 1.05)
        alpha_chan = np.clip(alpha_chan + edge * 0.5, 0.0, 1.0)

        # Orbital Rings (tilted ellipse behind & in front of sphere)
        # Ring 1
        ring_r = radius * 1.45
        ring_thickness = radius * 0.08
        tilt_y = (y_coords - local_cy) / 0.38
        ring_dist = np.sqrt(dx * dx * radius * radius + tilt_y * tilt_y)
        ring_mask = np.abs(ring_dist - ring_r) < ring_thickness
        
        # Ring lighting
        ring_lum = (0.6 + 0.4 * np.sin(dx * 3.0 + time_sec * 2.0)) * ring_mask
        r_chan[ring_mask] = np.maximum(r_chan[ring_mask], ring_lum[ring_mask] * (accent_rgb[0] / 255.0))
        g_chan[ring_mask] = np.maximum(g_chan[ring_mask], ring_lum[ring_mask] * (accent_rgb[1] / 255.0))
        b_chan[ring_mask] = np.maximum(b_chan[ring_mask], ring_lum[ring_mask] * (accent_rgb[2] / 255.0))
        alpha_chan[ring_mask] = np.maximum(alpha_chan[ring_mask], 0.85)

        # Convert to 8-bit RGBA
        r_u8 = np.clip(r_chan * 255.0, 0, 255).astype(np.uint8)
        g_u8 = np.clip(g_chan * 255.0, 0, 255).astype(np.uint8)
        b_u8 = np.clip(b_chan * 255.0, 0, 255).astype(np.uint8)
        a_u8 = np.clip(alpha_chan * 255.0, 0, 255).astype(np.uint8)

        rgba = np.dstack((r_u8, g_u8, b_u8, a_u8))
        sphere_img = Image.fromarray(rgba, mode="RGBA")
        return sphere_img

    def render_frame(
        self,
        scene: KineticSceneSpec,
        local_time: float,
        width: int,
        height: int,
        is_transitioning: bool = False,
        transition_progress: float = 0.0,
    ) -> Image.Image:
        """Renders a single high-impact 1080x1920 frame."""
        t_norm = min(1.0, local_time / scene.duration)
        enter_ease = ease_out_expo(min(1.0, local_time / 0.85))
        
        # Color parsing
        accent_hex = scene.accent_color.lstrip("#")
        accent_rgb = tuple(int(accent_hex[i : i + 2], 16) for i in (0, 2, 4))
        if len(accent_rgb) != 3:
            accent_rgb = (0, 240, 255)

        # 1. Background: Deep obsidian/midnight gradient with subtle architectural grid
        bg = Image.new("RGB", (width, height), color=(8, 12, 22))
        draw_bg = ImageDraw.Draw(bg)

        # Radial vignette gradient
        cx, cy = width / 2.0, height * 0.45
        for r_step in range(12):
            grad_r = int(max(width, height) * (1.0 - r_step * 0.08))
            alpha_step = int(14 * (1.0 - r_step / 12.0))
            glow_color = (
                int(accent_rgb[0] * 0.08 * (1.0 - r_step / 12.0)),
                int(accent_rgb[1] * 0.08 * (1.0 - r_step / 12.0)),
                int(accent_rgb[2] * 0.12 * (1.0 - r_step / 12.0)),
            )
            draw_bg.ellipse((cx - grad_r, cy - grad_r, cx + grad_r, cy + grad_r), fill=glow_color)

        # Subtle engineering grid lines
        grid_step = int(width * 0.1)
        grid_color = (25, 35, 55)
        for gx in range(0, width, grid_step):
            draw_bg.line((gx, 0, gx, height), fill=grid_color, width=1)
        for gy in range(0, height, grid_step):
            draw_bg.line((0, gy, width, gy), fill=grid_color, width=1)

        # 2. 3D Procedural Chrome Sphere in center-upper background
        # Sphere camera motion: continuous slow drift / breathing
        camera_scale = 1.0 + 0.15 * math.sin(local_time * 0.8)
        if scene.camera_motion == "dolly_in":
            camera_scale = 1.0 + 0.25 * t_norm
        elif scene.camera_motion == "zoom_burst":
            camera_scale = 0.85 + 0.45 * enter_ease

        sphere_radius = int(width * 0.26 * camera_scale)
        sphere_cx = width * 0.5 + 30.0 * math.sin(local_time * 0.5)
        sphere_cy = height * 0.38 + 20.0 * math.cos(local_time * 0.7)

        sphere_img = self._render_chrome_sphere(
            width, height, sphere_cx, sphere_cy, sphere_radius, local_time, accent_rgb
        )
        # Paste sphere onto background
        paste_x = int(sphere_cx - sphere_img.width / 2.0)
        paste_y = int(sphere_cy - sphere_img.height / 2.0)
        bg.paste(sphere_img, (paste_x, paste_y), sphere_img)

        # 3. Kicker & Telemetry Overlays
        draw = ImageDraw.Draw(bg)
        kicker_font = self._get_font(int(width * 0.024))
        kicker_text = f"// {scene.kicker.upper()} [FRAME-ACCURATE // 30FPS]"
        kicker_y = int(height * 0.08)
        draw.text((int(width * 0.08), kicker_y), kicker_text, font=kicker_font, fill=accent_rgb)

        # Header accent rule
        draw.line(
            (int(width * 0.08), kicker_y + int(width * 0.035), int(width * 0.92), kicker_y + int(width * 0.035)),
            fill=(45, 60, 90),
            width=2,
        )
        # Running progress bar
        draw.line(
            (
                int(width * 0.08),
                kicker_y + int(width * 0.035),
                int(width * 0.08 + width * 0.84 * t_norm),
                kicker_y + int(width * 0.035),
            ),
            fill=accent_rgb,
            width=3,
        )

        # 4. Monumental Screen-Filling Typography
        # Auto-wrap headline into large, commanding impact lines
        words = scene.headline.upper().split()
        lines: List[str] = []
        cur_line = ""
        for w in words:
            if not cur_line:
                cur_line = w
            elif len(cur_line) + len(w) <= 14:
                cur_line += f" {w}"
            else:
                lines.append(cur_line)
                cur_line = w
        if cur_line:
            lines.append(cur_line)

        # Calculate optimal monumental font size to fill the lower half
        font_size = int(width * 0.125)  # Massive ~135px on 1080w
        title_font = self._get_font(font_size)
        line_height = int(font_size * 1.08)

        text_start_y = int(height * 0.58)

        for line_idx, line in enumerate(lines):
            # Per-line kinetic reveal: staggered pop-in with upward momentum
            line_stagger = line_idx * 0.12
            line_local_t = max(0.0, (local_time - line_stagger) / 0.5)
            line_ease = ease_out_back(min(1.0, line_local_t), s=1.4)

            # Upward motion offset
            offset_y = int((1.0 - line_ease) * 80.0)
            cur_y = text_start_y + line_idx * line_height + offset_y

            # Measure text width
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_w = bbox[2] - bbox[0]
            # Center alignment with slight left-bias for modern editorial poster look
            text_x = int(width * 0.08)

            # Drop shadow / glow
            shadow_color = (0, 0, 0)
            draw.text((text_x + 4, cur_y + 4), line, font=title_font, fill=shadow_color)

            # Kinetic text fill: bright white with subtle accent tint
            text_color = (255, 255, 255) if line_idx == 0 else (220, 235, 255)
            draw.text((text_x, cur_y), line, font=title_font, fill=text_color)

        # 5. Editorial Subtitle / Manifesto description
        if scene.subhead:
            sub_font = self._get_font(int(width * 0.032))
            sub_y = text_start_y + len(lines) * line_height + int(height * 0.02)
            sub_bbox = draw.textbbox((0, 0), scene.subhead, font=sub_font)
            sub_color = (160, 180, 215)
            draw.text((int(width * 0.08), sub_y), scene.subhead, font=sub_font, fill=sub_color)

        # 6. Bottom Brand & Coordinates Bar
        bot_y = int(height * 0.93)
        draw.line((int(width * 0.08), bot_y - 10, int(width * 0.92), bot_y - 10), fill=(40, 50, 75), width=1)
        coord_text = f"HINAA OS // CORE RUNTIME 3.0 · LATENCY P95: 14MS · REEL-ID: {hash(scene.headline) % 999999:06d}"
        coord_font = self._get_font(int(width * 0.018))
        draw.text((int(width * 0.08), bot_y), coord_text, font=coord_font, fill=(100, 120, 160))

        # 7. Chromatic Aberration & Lens Transitions (if whip/transition active)
        if is_transitioning and transition_progress > 0.0:
            # Chromatic split
            split_px = int(transition_progress * 18.0)
            if split_px > 0:
                r, g, b = bg.split()
                # Shift R left, B right
                r_shifted = ImageChops.offset(r, -split_px, 0)
                b_shifted = ImageChops.offset(b, split_px, 0)
                bg = Image.merge("RGB", (r_shifted, g, b_shifted))

        return bg


class KineticReelCompiler:
    """Orchestrates multi-scene rendering and high-bitrate FFmpeg compilation."""

    def __init__(self):
        self.renderer = KineticMotionRenderer()

    def find_ffmpeg(self) -> str:
        candidates = [
            shutil.which("ffmpeg"),
            "C:/Users/unesh/AppData/Local/Microsoft/WinGet/Links/ffmpeg.EXE",
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
        ]
        for c in candidates:
            if c and Path(c).exists():
                return str(c)
        raise RuntimeError("FFmpeg executable not found on host machine.")

    def render_reel(
        self,
        spec: KineticReelSpec,
        output_path: Path,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Path:
        """Renders complete kinetic reel to high-bitrate MP4."""
        ffmpeg_exe = self.find_ffmpeg()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="hina_kinetic_") as tmpdir:
            tmp_path = Path(tmpdir)
            frames_dir = tmp_path / "frames"
            frames_dir.mkdir(parents=True, exist_ok=True)

            total_duration = sum(s.duration for s in spec.scenes)
            total_frames = int(total_duration * spec.fps)

            frame_idx = 0
            scene_start_frame = 0

            for scene_idx, scene in enumerate(spec.scenes):
                scene_frames = int(scene.duration * spec.fps)

                for f in range(scene_frames):
                    local_time = f / spec.fps
                    # Transition detection (last 6 frames of scene)
                    is_trans = f >= (scene_frames - 6) and (scene_idx < len(spec.scenes) - 1)
                    trans_prog = (f - (scene_frames - 6)) / 6.0 if is_trans else 0.0

                    img = self.renderer.render_frame(
                        scene=scene,
                        local_time=local_time,
                        width=spec.width,
                        height=spec.height,
                        is_transitioning=is_trans,
                        transition_progress=trans_prog,
                    )

                    frame_file = frames_dir / f"frame_{frame_idx:05d}.png"
                    img.save(frame_file, format="PNG")
                    frame_idx += 1

                    if progress_callback and frame_idx % 15 == 0:
                        pct = (frame_idx / total_frames) * 85.0
                        progress_callback(pct, f"Rendered frame {frame_idx}/{total_frames}")

            if progress_callback:
                progress_callback(88.0, "Encoding master MP4 with FFmpeg...")

            # FFmpeg high-bitrate assembly
            cmd = [
                ffmpeg_exe,
                "-y",
                "-framerate", str(spec.fps),
                "-i", str(frames_dir / "frame_%05d.png"),
            ]

            # Optional audio track overlay
            if spec.audio_path and Path(spec.audio_path).exists():
                cmd.extend(["-i", str(spec.audio_path), "-c:a", "aac", "-b:a", "192k", "-shortest"])

            cmd.extend([
                "-c:v", "libx264",
                "-profile:v", "high",
                "-level:v", "4.2",
                "-preset", "medium",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(output_path),
            ])

            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg render failed (code {res.returncode}): {res.stderr[-600:]}")

            if progress_callback:
                progress_callback(100.0, "Reel compilation complete!")

        return output_path
