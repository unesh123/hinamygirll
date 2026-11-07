# Avatar pipeline: sourcing a high-fidelity model

HINAA renders two kinds of model. Both are driven by the same face engine
(`apps/web/src/features/avatar/face/`), which blends 12 emotions into VRM presets
and the ARKit 52 blendshapes, lip-syncs from the playing TTS audio, and runs
eyes, blinks, micro-expressions and body motion.

| Kind (runtime-detected) | What it is | How it is driven |
| --- | --- | --- |
| `vrm-preset` | VRM with only the standard presets (VRoid default) | Existing preset pipeline plus audio lip-sync and micro-expression flickers |
| `vrm-perfectsync` | VRM that also exposes ARKit-named custom expressions | Everything above plus brows, cheeks, nose, mouth corners, tongue, etc. driven per-blendshape |
| `glb-arkit` | Plain GLB whose face meshes carry ARKit 52 morph targets | Fully morph-driven face, procedural body bones, `MeshPhysicalMaterial` skin/hair/eye upgrade, AgX tone mapping, key/fill/rim lighting |
| `glb-basic` | GLB without usable face morphs | Body motion only (breathing, weight shift, nods) |

Detection is automatic (`detectModelCapability`): a model counts as ARKit-driven when it
has at least 40% of the 52 names **and** the core set `eyeBlinkLeft/Right`, `jawOpen`,
`mouthSmileLeft/Right`. Names are matched case-insensitively, and `L`/`R` suffixes and
separators are tolerated (`EyeBlinkLeft`, `mouthSmile_R`).

## License warning: replace the default model before any public demo

The bundled default `apps/web/public/models/hinaa.vrm` (also stored as `model_7903.vrm`)
is **Libby_free** by `rurune`. Its embedded VRM terms **disallow commercial use**.
It is fine for personal or local use only. Every other bundled VRM currently has an
unverified licence (see `docs/ASSET_LICENSES.md`). Before a public demo, investor
demo, or release, replace the default with a model you hold written commercial
rights for. The registry marks these entries `license: "non-commercial"` or
`"unverified"`; only `"licensed"` entries are safe to ship.

## Option A: commission a VRM with PerfectSync

Best fit for the stylised anime look.

1. Commission or buy a VRoid/Blender-built character with **PerfectSync** expressions.
   Get written permission for commercial use, modification, redistribution inside a web app,
   and AI-driven animation.
2. Required expression names, in the ARKit 52 set (PerfectSync capitalises the first
   letter; both spellings work):
   `BrowDownLeft/Right, BrowInnerUp, BrowOuterUpLeft/Right, CheekPuff, CheekSquintLeft/Right,
   EyeBlinkLeft/Right, EyeLookDown/In/Out/UpLeft/Right, EyeSquintLeft/Right, EyeWideLeft/Right,
   JawForward, JawLeft, JawOpen, JawRight, MouthClose, MouthDimpleLeft/Right,
   MouthFrownLeft/Right, MouthFunnel, MouthLeft, MouthLowerDownLeft/Right, MouthPressLeft/Right,
   MouthPucker, MouthRight, MouthRollLower/Upper, MouthShrugLower/Upper, MouthSmileLeft/Right,
   MouthStretchLeft/Right, MouthUpperUpLeft/Right, NoseSneerLeft/Right, TongueOut`.
3. Keep the standard VRM presets (`happy`, `angry`, `sad`, `relaxed`, `surprised`, `aa`, `ih`,
   `ou`, `ee`, `oh`, `blink`) so non-ARKit paths still work.
4. Drop it into `apps/web/public/models/` and register it (see "Registering a model").

## Option B: realistic human GLB with ARKit 52 morph targets

Best fit for a human-level look. Sources that export ARKit-52 morph targets:
Reallusion Character Creator 4 (plus the Blender pipeline), MetaHuman exported through
Blender, Ready Player Me (enable `morphTargets=ARKit`), or a commissioned custom head
from a scanning/character studio.

Requirements:

- Morph targets named with the ARKit 52 names (any casing, see above) on the face meshes.
  Teeth and tongue meshes may carry their own copies; every mesh that owns a name is driven.
- A humanoid skeleton. Bones are matched by name for body motion: `Hips`, `Spine`, `Spine1`
  or `Spine2` or `Chest`, `Neck`, `Head`, `LeftShoulder`/`RightShoulder` (Mixamo, CC4
  and RPM prefixes such as `mixamorig:` and `CC_Base_` are stripped). Missing bones are
  skipped, never an error.
- PBR materials (`MeshStandardMaterial` when loaded). Skin, hair and eye materials are
  recognised by material or mesh name (`skin|body|face|head`, `hair|brow|lash`, `eye|cornea`)
  and upgraded to `MeshPhysicalMaterial` with sheen (soft skin and hair rim) and clearcoat
  (wet cornea). Name them accordingly.
- Albedo/emissive textures are treated as sRGB, data maps (normal, roughness, AO) stay linear.
- Face forward along +Z, feet at or near y = 0. The loader normalises height to 1.65 m,
  puts the feet on the floor and centres the model; fine-tune with the presentation controls.
- Licence: written commercial rights for web redistribution and real-time animation.
  Photo-scanned humans also need a likeness/biometric release from the person scanned.

## Compression (do this before committing)

Raw CC4/MetaHuman exports are 50–300 MB. Target under 15 MB for the web.

```bash
npm i -g @gltf-transform/cli
# 1. Weld, dedupe, prune. Keep the ARKit morph targets (never use --no-morph or simplify faces hard).
gltf-transform optimize in.glb out.glb \
  --compress meshopt \
  --texture-compress ktx2 \
  --texture-size 2048 \
  --simplify false
```

- **Meshopt** geometry compression is decoded in-browser (`MeshoptDecoder` is wired into
  `GlbHumanAvatar`). Use the `quantize` filter carefully on morph targets; check the face
  after compressing.
- **KTX2 / Basis** textures need the transcoder served from `/basis/`. Copy
  `node_modules/three/examples/jsm/libs/basis/basis_transcoder.{js,wasm}` into
  `apps/web/public/basis/`. If you ship PNG/JPEG textures instead, skip this.
- Use 2K for face and body, 1K for hair cards and clothing, 512 for teeth/eyes.
- Verify the morph names survived: `gltf-transform inspect out.glb` lists them per mesh.

## Registering a model

Add the file to `apps/web/public/models/`, then in `features/avatar/avatarRegistry.ts`
(or at runtime with `registerAvatar`):

```ts
{
  id: "hinaa-human",
  name: "Hinaa (Realistic)",
  description: "Licensed realistic human GLB",
  fileUrl: "/models/hinaa-human.glb",
  companionId: "hinaa",
  format: "glb",            // inferred from .glb/.gltf; set it for extension-less URLs
  capability: "glb-arkit",  // declared hint; runtime detection is authoritative
  license: "licensed",
}
```

Record provenance, licence terms and SHA-256 in `docs/ASSET_LICENSES.md`
before the model is loaded in a release build.

## Runtime behaviour worth knowing

- **Lip-sync:** when TTS plays through the app's Web Audio graph, a derived 1024-point
  `AnalyserNode` (`features/audio/speechAnalyserTap.ts`) feeds the formant estimator, which
  produces `aa/ih/ou/ee/oh`, `jawOpen`, `mouthFunnel`, `mouthPucker` and `mouthClose`.
  When no analyser signal exists (browser speech synthesis), the text-timed visemes
  remain in charge.
- **Rendering:** GLB humans use AgX tone mapping, sRGB output, a key/fill/rim rig and soft
  shadows. VRM toon models keep their existing look and gain a gentle rim light.
  `prefers-reduced-motion` damps micro-motion and caps DPR. Low-power mode (device memory
  or core-count hints, or `localStorage["hinaa.low-power"] = "1"`) forces DPR 1, disables
  shadows and antialiasing. No postprocessing dependency is shipped; the quality
  struct exposes a `postprocessing` gate for a future lazy-loaded DoF/bloom pass.
- **Not covered by the engine:** hair/cloth physics for GLB (use baked hair cards), hand
  and finger animation for GLB, and full-body gestures for GLB. VRM models keep the existing
  gesture system.
