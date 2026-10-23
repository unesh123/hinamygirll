---
name: hina-sakuga-director
description: blixvip/html-anime Genga shot-sheet rules, 24fps katana smear timing, and First-Last-Frame (FLF) video pipeline
---

# Sakuga HTML-Anime & Keyframe Video Director

## 1. Frame-by-Frame Cel Architecture (blixvip/html-anime)
Rather than blurry diffusion artifacts, anime cels are drawn deterministically in HTML, SVG, and CSS, compiled through HyperFrames timing:
- **On-Twos (12 fps)**: Standard character acting, subtle breathing, eye tracking, dialogue head tilts.
- **On-Ones (24 fps)**: High-speed action climaxes (katana slashes, sparks, projectile impacts, rain sweeps) with 1-2 hand-drawn smear frames and a 12-frame settle hold.

## 2. Locked Shot Budget Rules
- 8-second film: 3 key drawings for establishing shots; 1 dedicated Sakuga action shot with 8 unique frame cels.
- 12-second film: 4 key drawings + 1 Sakuga climax (10 cels).
- 20-second film: 6 key drawings + 2 Sakuga climaxes (16 cels).

## 3. Strict Color Palettes & Cel Shading
- Restricted locked hex scripts: `indigo`, `eclipse`, `noon`, or `festival`.
- Zero blurry airbrushing: flat cel paint with a single hard-edged shadow at 20% ink opacity.

## 4. First-Last-Frame (FLF) Video Generation Pipeline
For photorealistic and cinematic video generation outside 2D anime:
1. Generate keyframe pairs: Frame 0 (Establish) and Frame 120 (Climax).
2. Lock character consistency via ControlNet/Depth reference masks.
3. Feed consecutive keyframe pairs into FLF models (Kling 2.0 / Wan 2.1) for frame-accurate camera and motion control.
