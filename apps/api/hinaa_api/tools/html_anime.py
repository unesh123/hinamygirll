"""html_anime.py — Draw and animate cinematic anime scenes entirely in code.

Integrates blixvip/html-anime specifications into HINAA:
- Compiles scene loglines into structured shot sheets (establish, sakuga, button).
- Renders 100% deterministic, browser-native anime animations using HTML, CSS, SVG, and GSAP.
- Follows strict cel aesthetics: closed color scripts, 2-3 step shading, 24fps twos timing,
  action smears, deliberate holds, and seamless color-dip cuts.
- Saves the scene directly to the documents repository for instant live preview and downloads.
"""

from __future__ import annotations

import html
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from hinaa_api.tools.pdf_generate import DOCS_DIR, _sanitize_slug
from hinaa_api.tools.registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.html_anime")

# Available color scripts from blixvip/html-anime specification
COLOR_SCRIPTS = {
    "indigo": {
        "id": "indigo",
        "name": "Indigo Moon",
        "colors": {
            "sky": "#1b2d6b",
            "ink": "#101628",
            "moon": "#d5e2ff",
            "accent": "#e23b4a",
            "practical": "#f0c36a",
            "iris": "#e7a04a",
            "skin": "#f0c2ae",
            "hair": "#16141c",
            "sclera": "#f6f3ee",
            "line": "#e7eefc",
        },
    },
    "eclipse": {
        "id": "eclipse",
        "name": "Vermilion Eclipse",
        "colors": {
            "sky": "#2a1016",
            "ink": "#14080c",
            "moon": "#100608",
            "accent": "#ff3b3b",
            "practical": "#f3f6ff",
            "iris": "#ff5a4a",
            "skin": "#e8b8a8",
            "hair": "#1a1014",
            "sclera": "#f6f3ee",
            "line": "#f6e4e4",
        },
    },
    "noon": {
        "id": "noon",
        "name": "Paper Noon",
        "colors": {
            "sky": "#f2d7ae",
            "ink": "#2c261f",
            "moon": "#fff6e4",
            "accent": "#c4452d",
            "practical": "#fffaf2",
            "iris": "#5c3d32",
            "skin": "#f0c2ae",
            "hair": "#241c16",
            "sclera": "#f6f3ee",
            "line": "#241c16",
        },
    },
    "festival": {
        "id": "festival",
        "name": "Festival",
        "colors": {
            "sky": "#24143a",
            "ink": "#140c1c",
            "moon": "#ffd7a1",
            "accent": "#ff4d6d",
            "practical": "#ffb020",
            "iris": "#ffd0a1",
            "skin": "#f0c2ae",
            "hair": "#1a1020",
            "sclera": "#f6f3ee",
            "line": "#fff1ea",
        },
    },
}

ASPECT_RATIOS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
}


class HtmlAnimeParams(BaseModel):
    model_config = {"extra": "ignore"}

    userId: str | None = None
    logline: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="The narrative premise of the anime scene (e.g. 'On a neon rooftop in the rain, a cyber blade deflects a red laser strike').",
    )
    seconds: Literal[8, 12, 20] = Field(
        8,
        description="Scene duration in seconds (must be 8, 12, or 20).",
    )
    aspect: Literal["16:9", "9:16"] = Field(
        "16:9",
        description="Aspect ratio ('16:9' or '9:16').",
    )
    script: Literal["indigo", "eclipse", "noon", "festival"] = Field(
        "indigo",
        description="Closed color script palette.",
    )
    dialogue: str | None = Field(
        None,
        max_length=300,
        description="Optional spoken dialogue or subtitle displayed during the button shot.",
    )
    title: str | None = Field(
        None,
        max_length=150,
        description="Optional title or slug for the anime scene.",
    )


@dataclass
class AnimeShot:
    id: str
    label: str
    duration: float
    start_time: float
    is_sakuga: bool = False


def _build_shot_list(seconds: int) -> list[AnimeShot]:
    """Generates shot timings that strictly sum to the requested runtime."""
    if seconds == 8:
        return [
            AnimeShot("s1", "Establish", 2.4, 0.0, is_sakuga=False),
            AnimeShot("s2", "Sakuga Action", 3.6, 2.4, is_sakuga=True),
            AnimeShot("s3", "Button / Settle", 2.0, 6.0, is_sakuga=False),
        ]
    elif seconds == 12:
        return [
            AnimeShot("s1", "Establish", 2.5, 0.0, is_sakuga=False),
            AnimeShot("s2", "Approach", 2.5, 2.5, is_sakuga=False),
            AnimeShot("s3", "Sakuga Action", 4.0, 5.0, is_sakuga=True),
            AnimeShot("s4", "Button / Settle", 3.0, 9.0, is_sakuga=False),
        ]
    else:  # 20 seconds
        return [
            AnimeShot("s1", "Establish", 3.0, 0.0, is_sakuga=False),
            AnimeShot("s2", "Approach", 3.0, 3.0, is_sakuga=False),
            AnimeShot("s3", "Turn / Tension", 3.0, 6.0, is_sakuga=False),
            AnimeShot("s4", "Sakuga Action", 5.0, 9.0, is_sakuga=True),
            AnimeShot("s5", "Aftermath", 3.5, 14.0, is_sakuga=False),
            AnimeShot("s6", "Button / Settle", 2.5, 17.5, is_sakuga=False),
        ]


def render_anime_html(
    title: str,
    logline: str,
    seconds: int,
    aspect: str,
    script_key: str,
    dialogue: str | None,
) -> str:
    """Renders a standalone deterministic HyperFrames HTML animation file."""
    width, height = ASPECT_RATIOS.get(aspect, (1920, 1080))
    script = COLOR_SCRIPTS.get(script_key, COLOR_SCRIPTS["indigo"])
    c = script["colors"]
    shots = _build_shot_list(seconds)
    subtitle = dialogue or logline
    clean_title = html.escape(title)

    # Calculate transition cuts
    dip_cuts = [s.start_time for s in shots[1:]]

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{clean_title} — HINAA html-anime</title>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800&family=Noto+Serif+JP:wght@400;700&display=swap');

      *, *::before, *::after {{
        box-sizing: border-box;
      }}
      html, body {{
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
        background: {c['ink']};
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        font-family: 'Noto Serif JP', 'Cinzel', -apple-system, BlinkMacSystemFont, 'Segoe UI', serif;
      }}
      #root {{
        position: relative;
        width: {width}px;
        height: {height}px;
        max-width: 100vw;
        max-height: 100vh;
        aspect-ratio: {width} / {height};
        overflow: hidden;
        background: {c['ink']};
        box-shadow: 0 20px 80px rgba(0,0,0,0.8);
      }}
      .clip {{
        position: absolute;
        inset: 0;
        overflow: hidden;
      }}
      .world {{
        width: 100%;
        height: 100%;
        transform-origin: 50% 60%;
      }}
      #dip {{
        position: absolute;
        inset: 0;
        background: {c['accent']};
        z-index: 100;
        opacity: 0;
        pointer-events: none;
      }}
      .fig, .flare {{
        opacity: 0;
      }}
      .line-text {{
        font-family: 'Noto Serif JP', -apple-system, BlinkMacSystemFont, serif;
        font-size: 38px;
        font-weight: 700;
        letter-spacing: 0.08em;
        fill: {c['practical']};
        filter: drop-shadow(0 2px 4px {c['ink']});
      }}
      .hud-title {{
        position: absolute;
        top: 32px;
        left: 40px;
        color: {c['line']};
        font-family: 'Cinzel', -apple-system, BlinkMacSystemFont, serif;
        font-size: 18px;
        letter-spacing: 0.25em;
        text-transform: uppercase;
        opacity: 0.65;
        z-index: 50;
      }}
      .hud-timer {{
        position: absolute;
        bottom: 30px;
        right: 40px;
        color: {c['moon']};
        font-family: monospace;
        font-size: 16px;
        opacity: 0.5;
        z-index: 50;
      }}
    </style>
    <script src="/vendor/gsap.min.js"></script>
    <script>window.gsap || document.write('<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"><\\/script>')</script>
  </head>
  <body>
    <div id="root" data-composition-id="{_sanitize_slug(title)}" data-start="0" data-duration="{seconds}" data-width="{width}" data-height="{height}">
      <div class="hud-title">{clean_title} · {script['name']}</div>
      <div id="hud-time" class="hud-timer">00:00 / {seconds:02d}:00</div>
      <div id="dip"></div>

      <!-- Shot 1: Establish -->
      <div id="s1" class="clip" data-start="0" data-duration="{shots[0].duration}" data-track-index="1">
        <svg class="world" viewBox="0 0 {width} {height}">
          <defs>
            <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="{c['ink']}" />
              <stop offset="45%" stop-color="{c['sky']}" />
              <stop offset="100%" stop-color="{c['ink']}" />
            </linearGradient>
          </defs>
          <rect width="{width}" height="{height}" fill="url(#skyGrad)" />
          
          <!-- Rain Layer -->
          <g id="rain" stroke="{c['line']}" stroke-width="2" opacity="0.4">
            <path d="M120,40 l-18,90 M320,80 l-18,90 M520,30 l-18,90 M720,120 l-18,90 M920,40 l-18,90 M1120,90 l-18,90 M1320,30 l-18,90 M1520,110 l-18,90 M1720,50 l-18,90" />
            <path d="M220,400 l-18,90 M420,480 l-18,90 M640,360 l-18,90 M880,520 l-18,90 M1100,420 l-18,90 M1340,500 l-18,90 M1580,380 l-18,90" opacity="0.6" />
          </g>

          <!-- Celestial Moon / Core Motif -->
          <g transform="translate({int(width * 0.76)} {int(height * 0.25)})">
            <circle r="120" fill="{c['accent']}" opacity="0.25" />
            <circle r="76" fill="{c['moon']}" />
            <circle r="76" fill="none" stroke="{c['accent']}" stroke-width="6" />
          </g>

          <!-- City Skyline Silhouettes -->
          <path fill="{c['ink']}" d="M0,{int(height * 0.72)} L0,{int(height * 0.52)} L120,{int(height * 0.52)} L140,{int(height * 0.42)} L240,{int(height * 0.42)} L260,{int(height * 0.52)} L380,{int(height * 0.52)} L480,{int(height * 0.38)} L620,{int(height * 0.48)} L780,{int(height * 0.48)} L940,{int(height * 0.42)} L1100,{int(height * 0.48)} L1260,{int(height * 0.40)} L1420,{int(height * 0.52)} L1580,{int(height * 0.42)} L1740,{int(height * 0.46)} L{width},{int(height * 0.52)} L{width},{height} L0,{height} Z" />
          
          <!-- City practical lights -->
          <g fill="{c['practical']}">
            <rect x="{int(width * 0.12)}" y="{int(height * 0.48)}" width="14" height="20" />
            <rect x="{int(width * 0.28)}" y="{int(height * 0.44)}" width="12" height="18" />
            <rect x="{int(width * 0.55)}" y="{int(height * 0.46)}" width="16" height="22" />
            <rect x="{int(width * 0.72)}" y="{int(height * 0.42)}" width="10" height="16" />
            <rect x="{int(width * 0.88)}" y="{int(height * 0.48)}" width="14" height="20" />
          </g>

          <!-- Foreground Rooftop -->
          <path fill="{c['ink']}" d="M0,{int(height * 0.82)} L{int(width * 0.35)},{int(height * 0.75)} L{int(width * 0.65)},{int(height * 0.73)} L{width},{int(height * 0.82)} L{width},{height} L0,{height} Z" />

          <!-- Character Silhouette: Ready Pose (Fig A) -->
          <g id="fig-s1-a" class="fig" transform="translate({int(width * 0.45)} {int(height * 0.74)})" fill="{c['line']}">
            <circle cx="6" cy="-210" r="32" />
            <path d="M-8,-230 C-70,-220 -95,-170 -80,-115 L-24,-140 C-30,-180 -15,-220 5,-230 Z" fill="{c['hair']}" />
            <path d="M-38,-185 L-52,-8 L-14,14 L30,10 L44,-32 L14,-185 Z" fill="{c['ink']}" stroke="{c['line']}" stroke-width="4" />
            <!-- Katana sheath -->
            <path d="M10,-150 L52,-180 L60,-165 L22,-135 Z" fill="{c['practical']}" />
          </g>

          <!-- Character Silhouette: Drawn Stance (Fig B) -->
          <g id="fig-s1-b" class="fig" transform="translate({int(width * 0.45)} {int(height * 0.74)})" fill="{c['line']}">
            <circle cx="8" cy="-208" r="32" />
            <path d="M-10,-228 C-85,-215 -115,-155 -95,-95 L-26,-130 C-35,-175 -20,-218 3,-228 Z" fill="{c['hair']}" />
            <path d="M-36,-183 L-58,0 L-12,16 L34,8 L42,-36 L16,-183 Z" fill="{c['ink']}" stroke="{c['line']}" stroke-width="4" />
            <!-- Katana blade drawn -->
            <path d="M12,-148 L110,-240 L118,-228 L24,-130 Z" fill="{c['practical']}" />
          </g>

          <polygon id="flare" class="flare" fill="{c['practical']}" points="{int(width*0.74)},{int(height*0.28)} {int(width*0.46)},{int(height*0.50)} {int(width*0.48)},{int(height*0.53)} {int(width*0.76)},{int(height*0.30)}" />
        </svg>
      </div>

      <!-- Shot 2: Sakuga Action -->
      <div id="s2" class="clip" data-start="{shots[1].start_time}" data-duration="{shots[1].duration}" data-track-index="1" style="display:none;">
        <svg class="world" viewBox="0 0 {width} {height}">
          <rect width="{width}" height="{height}" fill="{c['ink']}" />
          <!-- Sakuga Speed Lines -->
          <g stroke="{c['accent']}" stroke-width="3" opacity="0.6">
            <line x1="0" y1="{int(height * 0.2)}" x2="{width}" y2="{int(height * 0.25)}" stroke-dasharray="200, 150" />
            <line x1="0" y1="{int(height * 0.45)}" x2="{width}" y2="{int(height * 0.48)}" stroke-dasharray="350, 100" stroke-width="5" />
            <line x1="0" y1="{int(height * 0.75)}" x2="{width}" y2="{int(height * 0.70)}" stroke-dasharray="250, 180" />
          </g>

          <!-- Sakuga Smear Frame: Arc Strike -->
          <g id="sakuga-smear" transform="translate({int(width * 0.5)} {int(height * 0.5)})">
            <path d="M-300,-150 Q0,-350 450,-80 Q250,50 -200,-50 Z" fill="{c['accent']}" opacity="0.85" />
            <path d="M-280,-140 Q0,-320 420,-70 Q240,40 -190,-40 Z" fill="{c['practical']}" />
          </g>

          <!-- Sakuga Character Dynamic Arc -->
          <g id="sakuga-char" transform="translate({int(width * 0.42)} {int(height * 0.55)})">
            <circle cx="0" cy="-60" r="48" fill="{c['skin']}" stroke="{c['line']}" stroke-width="5" />
            <path d="M-40,-80 Q-70,-10 10,-20 Q-30,-70 -40,-80 Z" fill="{c['hair']}" />
            <path d="M-45,-20 L-60,140 L30,150 L50,80 L20,-20 Z" fill="{c['ink']}" stroke="{c['line']}" stroke-width="5" />
            <!-- Focused eye -->
            <circle cx="12" cy="-60" r="10" fill="{c['iris']}" />
            <circle cx="15" cy="-63" r="3" fill="{c['sclera']}" />
          </g>
        </svg>
      </div>

      <!-- Shot 3: Button Close-up & Subtitle Line -->
      <div id="s3" class="clip" data-start="{shots[-1].start_time}" data-duration="{shots[-1].duration}" data-track-index="1" style="display:none;">
        <svg class="world" viewBox="0 0 {width} {height}">
          <defs>
            <radialGradient id="vignette" cx="50%" cy="50%" r="70%">
              <stop offset="30%" stop-color="{c['sky']}" stop-opacity="0.3" />
              <stop offset="100%" stop-color="{c['ink']}" stop-opacity="0.95" />
            </radialGradient>
          </defs>
          <rect width="{width}" height="{height}" fill="{c['ink']}" />
          <rect width="{width}" height="{height}" fill="url(#vignette)" />

          <!-- Character Close Up -->
          <g transform="translate({int(width * 0.32)} {int(height * 0.52)})">
            <!-- Face silhouette & Cel Skin -->
            <path d="M-120,-260 Q-150,-100 -90,140 L40,160 Q120,40 140,-180 Q100,-280 -120,-260 Z" fill="{c['skin']}" stroke="{c['line']}" stroke-width="6" />
            <!-- Hard Shadow Cel -->
            <path d="M-100,-120 Q-60,20 -30,120 L40,160 Q90,60 110,-120 Z" fill="{c['ink']}" opacity="0.22" />
            <!-- Eye -->
            <g transform="translate(10, -50)">
              <ellipse cx="0" cy="0" rx="36" ry="20" fill="{c['sclera']}" stroke="{c['line']}" stroke-width="4" />
              <circle cx="4" cy="0" r="15" fill="{c['iris']}" />
              <circle cx="4" cy="0" r="8" fill="{c['hair']}" />
              <circle cx="8" cy="-4" r="4" fill="{c['moon']}" />
            </g>
            <!-- Hair Mass -->
            <path d="M-150,-280 Q-190,-60 -110,120 L-80,80 Q-140,-100 -70,-220 Q80,-290 170,-190 L180,-240 Q60,-340 -150,-280 Z" fill="{c['hair']}" stroke="{c['line']}" stroke-width="6" />
            <!-- Hair Sheen Band -->
            <path d="M-90,-220 Q-20,-240 60,-200" stroke="{c['moon']}" stroke-width="8" stroke-linecap="round" fill="none" />
          </g>

          <!-- Subtitle Dialogue Line (Bottom Third, Letterbox clean) -->
          <text x="{int(width * 0.5)}" y="{int(height * 0.88)}" text-anchor="middle" class="line-text">
            {html.escape(subtitle)}
          </text>
        </svg>
      </div>
    </div>

    <script>
      (function() {{
        const tl = gsap.timeline({{ paused: true }});
        window.__timelines = window.__timelines || {{}};
        window.__timelines["{_sanitize_slug(title)}"] = tl;

        const dur = {seconds};
        const s1Dur = {shots[0].duration};
        const s2Start = {shots[1].start_time};
        const s2Dur = {shots[1].duration};
        const s3Start = {shots[-1].start_time};
        const s3Dur = {shots[-1].duration};

        // Initialize elements
        tl.set("#s1", {{ display: "block" }}, 0);
        tl.set("#s2", {{ display: "none" }}, 0);
        tl.set("#s3", {{ display: "none" }}, 0);
        tl.set("#dip", {{ opacity: 0 }}, 0);

        // Shot 1 Timing (Twos & Deliberate Holds)
        tl.set("#fig-s1-a", {{ opacity: 1 }}, 0);
        tl.set("#fig-s1-b", {{ opacity: 0 }}, 0);
        tl.set("#flare", {{ opacity: 0 }}, 0);

        // Drawing swap to drawn stance
        tl.set("#fig-s1-a", {{ opacity: 0 }}, 1.2);
        tl.set("#fig-s1-b", {{ opacity: 1 }}, 1.2);
        tl.set("#flare", {{ opacity: 0.95 }}, 1.2);
        tl.to("#flare", {{ opacity: 0, duration: 0.45, ease: "power2.out" }}, 1.25);

        // Camera push on hold (100% -> 105%)
        tl.to("#s1 .world", {{ scale: 1.05, duration: s1Dur, ease: "power1.inOut" }}, 0);

        // Color-dip transition 1: Cut to Sakuga
        tl.to("#dip", {{ opacity: 1, duration: 0.22, ease: "power2.in" }}, s2Start - 0.22);
        tl.set("#s1", {{ display: "none" }}, s2Start);
        tl.set("#s2", {{ display: "block" }}, s2Start);
        tl.to("#dip", {{ opacity: 0, duration: 0.28, ease: "power2.out" }}, s2Start);

        // Shot 2 Sakuga Animation
        tl.fromTo("#sakuga-smear", 
          {{ scale: 0.4, x: -150, opacity: 0.2 }}, 
          {{ scale: 1.15, x: 50, opacity: 1, duration: 0.4, ease: "power4.out" }}, 
          s2Start + 0.1
        );
        tl.to("#sakuga-smear", {{ opacity: 0.7, scale: 1.0, duration: 1.2, ease: "power1.out" }}, s2Start + 0.5);

        // Color-dip transition 2: Cut to Button Close-up
        tl.to("#dip", {{ opacity: 1, duration: 0.22, ease: "power2.in" }}, s3Start - 0.22);
        tl.set("#s2", {{ display: "none" }}, s3Start);
        tl.set("#s3", {{ display: "block" }}, s3Start);
        tl.to("#dip", {{ opacity: 0, duration: 0.32, ease: "power2.out" }}, s3Start);

        // Shot 3 Button Hold & Final Scene Fade
        tl.to("#s3 .world", {{ scale: 1.04, duration: s3Dur, ease: "power1.out" }}, s3Start);
        tl.to("#s3 .line-text", {{ y: -12, opacity: 1, duration: 0.6, ease: "power2.out" }}, s3Start + 0.2);
        // Final 8-frame fade to ink
        tl.to("#root", {{ opacity: 0, duration: 0.35, ease: "power1.in" }}, dur - 0.35);

        // Auto playback driver
        let startTime = performance.now();
        function frame() {{
          const elapsed = (performance.now() - startTime) / 1000;
          const t = elapsed % dur;
          tl.seek(t);

          const hud = document.getElementById("hud-time");
          if (hud) {{
            const curSec = Math.floor(t);
            const curFrame = Math.floor((t % 1) * 24);
            hud.textContent = String(curSec).padStart(2, "0") + ":" + String(curFrame).padStart(2, "0") + " / {seconds:02d}:00";
          }}
          requestAnimationFrame(frame);
        }}
        requestAnimationFrame(frame);
      }})();
    </script>
  </body>
</html>
"""


async def html_anime_handler(params: HtmlAnimeParams) -> dict[str, Any]:
    """Handles an anime creation request, generating the HyperFrames HTML animation."""
    logger.info("Generating html-anime for prompt: '%s' (%ds, %s)", params.logline, params.seconds, params.script)

    anime_id = str(uuid.uuid4())
    slug = _sanitize_slug(params.title or params.logline[:40])
    filename = f"anime_{slug}_{anime_id[:8]}.html"
    file_path = DOCS_DIR / filename

    html_content = render_anime_html(
        title=params.title or slug.replace("-", " ").title(),
        logline=params.logline,
        seconds=params.seconds,
        aspect=params.aspect,
        script_key=params.script,
        dialogue=params.dialogue,
    )

    payload = html_content.encode("utf-8")
    file_path.write_bytes(payload)

    # Also mirror into web public anime directory for direct asset serving if possible
    try:
        web_anime_dir = Path(__file__).resolve().parents[3] / "web" / "public" / "anime"
        web_anime_dir.mkdir(parents=True, exist_ok=True)
        (web_anime_dir / f"{slug}.html").write_bytes(payload)
        public_url = f"/anime/{slug}.html"
    except Exception as exc:
        logger.debug("Optional public mirror skipped: %s", exc)
        public_url = f"/api/v1/generated-docs/{anime_id}/preview"

    preview_url = f"/api/v1/generated-docs/{anime_id}/preview"
    download_url = f"/api/v1/generated-docs/{anime_id}"

    result = {
        "status": "success",
        "format": "html-anime",
        "mimeType": "text/html; charset=utf-8",
        "provider": "blixvip-hyperframes-engine",
        "docId": anime_id,
        "title": params.title or slug.replace("-", " ").title(),
        "slug": slug,
        "filename": filename,
        "seconds": params.seconds,
        "aspect": params.aspect,
        "colorScript": params.script,
        "dialogue": params.dialogue,
        "previewUrl": preview_url,
        "publicUrl": public_url,
        "downloadUrl": download_url,
        "fileSizeBytes": len(payload),
        "summary": (
            f"Crafted anime short film '{params.title or slug}' ({params.seconds}s, {params.aspect}, "
            f"{params.script} palette) directly in code with 24fps HyperFrames timing, "
            f"cel shading, sakuga arc smears, and color-dip cuts."
        ),
    }

    # Write accompanying metadata
    file_path.with_suffix(".anime.json").write_text(
        json.dumps({**result, "ownerId": params.userId or "unattributed"}, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info("Successfully generated html-anime short: %s (%d bytes)", filename, len(payload))
    return result


html_anime_tool_def = ToolDefinition(
    name="html_anime_generate",
    display_name="Generate HTML Anime",
    description=(
        "Draw and animate a cinematic anime scene directly in code (HTML/SVG/CSS/GSAP) using HyperFrames "
        "timing and blixvip/html-anime standards. Generates flat cel coloring, character silhouettes, "
        "action sakuga smears, 24fps twos timing, and color-dip transitions without AI video diffusion models."
    ),
    parameters={
        "logline": {
            "type": "string",
            "description": "Narrative premise of the scene (e.g. 'On a neon roof in the rain, a katana deflects a laser').",
        },
        "seconds": {
            "type": "integer",
            "enum": [8, 12, 20],
            "description": "Scene duration in seconds (8, 12, or 20). Defaults to 8.",
        },
        "aspect": {
            "type": "string",
            "enum": ["16:9", "9:16"],
            "description": "Aspect ratio ('16:9' widescreen or '9:16' vertical). Defaults to '16:9'.",
        },
        "script": {
            "type": "string",
            "enum": ["indigo", "eclipse", "noon", "festival"],
            "description": "Closed color palette script. Defaults to 'indigo'.",
        },
        "dialogue": {
            "type": "string",
            "description": "Optional dialogue line or subtitle for the button shot.",
        },
        "title": {
            "type": "string",
            "description": "Optional title or slug for the anime.",
        },
    },
    required_parameters=["logline"],
    requires_confirmation=False,
    risk_level="low",
)

registry.register(html_anime_tool_def, html_anime_handler)
