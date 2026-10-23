---
name: html-anime
description: Prompt an anime short film drawn and animated entirely in code (HTML, CSS, SVG, JavaScript) using HyperFrames timing. No video generation models, 100% deterministic, standalone execution.
---

# html-anime

You draw anime in code. You do not generate video with diffusion models, and you do not open an editor timeline.
The film is one standalone HTML file running at 24fps with deterministic HyperFrames timing and GSAP timeline synchronization.

## When to Use This Skill
- The user asks for code-drawn anime, an anime short in HTML, or HyperFrames anime animation.
- Scene descriptions needing stylized anime cinematography: holds, sakuga smear frames, flat cel coloring, rain layers, and closed color palettes.
- Building interactive browser-native anime sequences, intro sequences, or visual novels.

## Workflow

### 1. The Shot Sheet (Contract First)
If the user provides a logline, compile the brief first using `harness/compile.js`:
```js
import { compileBrief } from "./harness/compile.js";

const sheet = compileBrief({
  logline: "On a rainy neon roof, a blade catches the lightning before the strike.",
  seconds: 8,          // 8, 12, or 20
  aspect: "16:9",      // or "9:16"
  script: "indigo",    // indigo, eclipse, noon, or festival
  dialogue: "The rain hid the sound of the blade.",
});
```

### 2. Core Directing & Timing Rules
- **One Sakuga Shot**: The logline's core action verb is the sakuga shot. Every other shot is establish, approach, or button.
- **Budget**:
  - Sakuga shot gets up to 8 unique drawings (drawing swaps via `tl.set`).
  - Other shots get 3 drawings maximum.
  - Character animation is on **twos** (each drawing holds 2 frames at 24fps).
  - Rain, sparks, and blade swings are on **ones**.
  - Settle holds must last at least 12 frames.
- **Color Palettes (Strict)**:
  Use only the hexes from the selected color script (`indigo`, `eclipse`, `noon`, or `festival`). Do not introduce arbitrary new colors.
  - `indigo`: sky `#1b2d6b`, ink `#101628`, moon `#d5e2ff`, accent `#e23b4a`, practical `#f0c36a`, iris `#e7a04a`, skin `#f0c2ae`, hair `#16141c`, sclera `#f6f3ee`, line `#e7eefc`
  - `eclipse`: sky `#2a1016`, ink `#14080c`, moon `#100608`, accent `#ff3b3b`, practical `#f3f6ff`, iris `#ff5a4a`, skin `#e8b8a8`, hair `#1a1014`, sclera `#f6f3ee`, line `#f6e4e4`

### 3. Cel Painting & Aesthetics
- **Flat Cel Shading**: No soft Gaussian blurs, no CSS box-shadows, no airbrushed skin.
- **Shadows**: One hard-edged shadow shape per character, drawn with `ink` at ~20% opacity.
- **Depth Layers (Back to Front)**:
  1. Sky (gradient from `sky` to `ink`)
  2. Far silhouette (city/mountain skyline in `ink` with minimal `practical` windows)
  3. Ground / mid-ground silhouette
  4. Rain layer (individual straight stroke paths in `line`)
  5. Close figure / character cel
  6. Subtitle line / Type
- **Smears**: Action smears are drawn as stretched SVG silhouettes along the line of motion, not browser blur filters.

### 4. Camera & Cuts
- **No Fade-Ins**: Characters do not fade up from opacity 0.
- **Color-Dip Cut**: Transitions between shots are executed with a `#dip` overlay in `accent` or `ink`:
  ```js
  tl.set("#dip", { opacity: 0 }, 0);
  tl.to("#dip", { opacity: 1, duration: 0.25, ease: "power2.in" }, cut - 0.25);
  tl.to("#dip", { opacity: 0, duration: 0.35, ease: "power2.out" }, cut + 0.05);
  ```
- **Camera Holds**: The only allowable camera movement on a hold is a slow scale from 100% to 106% across the shot (`ease: "power1.inOut"`).

### 5. HyperFrames Composition Standard
The root element must specify:
```html
<div
  id="root"
  data-composition-id="film"
  data-start="0"
  data-duration="8"
  data-width="1920"
  data-height="1080"
></div>
```
Timeline registration:
```js
const tl = gsap.timeline({ paused: true });
window.__timelines = window.__timelines || {};
window.__timelines["film"] = tl;
```
Built synchronously. No async, no `setTimeout`, no `Math.random()` (use seeded / explicit numbers).

## Reference Files
- [compile.js](file:///c:/Users/unesh/OneDrive/all%20my%20cloud%20stroge/Desktop/APPS/HINAMYGIRL/.agents/skills/html-anime/harness/compile.js)
- [roof.html](file:///c:/Users/unesh/OneDrive/all%20my%20cloud%20stroge/Desktop/APPS/HINAMYGIRL/.agents/skills/html-anime/templates/roof.html)
- [direct.md](file:///c:/Users/unesh/OneDrive/all%20my%20cloud%20stroge/Desktop/APPS/HINAMYGIRL/.agents/skills/html-anime/references/direct.md)
- [cel.md](file:///c:/Users/unesh/OneDrive/all%20my%20cloud%20stroge/Desktop/APPS/HINAMYGIRL/.agents/skills/html-anime/references/cel.md)
- [timing.md](file:///c:/Users/unesh/OneDrive/all%20my%20cloud%20stroge/Desktop/APPS/HINAMYGIRL/.agents/skills/html-anime/references/timing.md)
- [camera.md](file:///c:/Users/unesh/OneDrive/all%20my%20cloud%20stroge/Desktop/APPS/HINAMYGIRL/.agents/skills/html-anime/references/camera.md)
- [render.md](file:///c:/Users/unesh/OneDrive/all%20my%20cloud%20stroge/Desktop/APPS/HINAMYGIRL/.agents/skills/html-anime/references/render.md)
