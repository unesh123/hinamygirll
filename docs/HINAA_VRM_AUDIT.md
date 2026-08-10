# HINAA VRM Asset Audit

Date: 2026-08-10 · Method: binary GLB/JSON chunk parse of the actual committed asset (no filename guessing), plus live render verification (screenshots in `docs/evidence/`).

## Asset inventory

| Slot | Status |
|---|---|
| `apps/web/public/models/hinaa.vrm` | **Not committed** (gitignored `*.vrm` — this is the drop-in slot for the owner's own VRoid export). Restored locally at runtime by copying the backup; the loader now also falls back to `hinaa.vrm.bak` automatically. |
| `apps/web/public/models/hinaa.vrm.bak` | **Committed, parsed below.** 19,272,696 bytes. SHA-256 `ef55df5369e197e8b7f696ef853f566be178f075a4887bb264da1b33be6f8ea0`. |
| `hiro.vrm` | Not present (documented optional slot). |

## Parsed profile — `hinaa.vrm.bak`

| Property | Value |
|---|---|
| Container | GLB v2 |
| VRM version | **VRM 1.0** (`VRMC_vrm`; also `VRMC_springBone`, `VRMC_materials_mtoon`, `KHR_materials_unlit`, `KHR_texture_transform`) |
| Model name | 聖翔院ターナローゼ ("Seishouin Turnarose") |
| Author | はにゃりん |
| License | VRM 1.0 license (`https://vrm.dev/licenses/1.0/`): avatar use **everyone**, redistribution **allowed**, modification **allowed**, commercial usage **personalNonProfit**, credit **required**, political/religious & antisocial usage **disallowed** |
| ⚠️ License note | `models/README.md` previously called this asset "MIT" — **incorrect**. Embedded meta says personal/non-profit + credit required. Do not ship commercially without re-licensing. `docs/ASSET_LICENSES.md` should be updated before any release. |
| Height (bounds) | 1.593 m (min `[-0.574, 0.000, -0.365]`, max `[0.574, 1.593, 0.217]`) — feet at y≈0 |
| Root orientation | VRM 1.0 convention: faces **+Z**. This is why the previous hard-coded `rotation.y = Math.PI` showed the back of her head; the loader now uses `VRMUtils.rotateVRM0()` (no-op for VRM 1.0, corrects VRM 0.x). |
| Meshes / nodes | 3 meshes, 274 nodes |
| Materials / textures | 19 materials (MToon), 29 textures / 27 images |
| Morph targets | up to 57 per primitive |

## Humanoid bones — 54 found

All required bones present: hips, spine, chest, **upperChest: absent**, neck, head, shoulders (L/R), full arm chains, full leg chains + toes, **both eyes** (`leftEye`/`rightEye` → gaze/look-at possible), and **all 30 finger bones** (thumb metacarpal→distal, index/middle/ring/little proximal→distal, both hands) → finger-level gestures are possible with this asset.

Missing (optional in spec): `upperChest`, `jaw`. Chest anchor math falls back from `upperChest` → `chest` (implemented in `AvatarPresence`).

## Expressions — verified in asset

| Group | Names |
|---|---|
| Emotions | `happy`, `angry`, `sad`, `relaxed`, `surprised`, `neutral` |
| Visemes | `aa`, `ih`, `ou`, `ee`, `oh` |
| Blink | `blink`, `blinkLeft`, `blinkRight` |

No custom expressions beyond presets. Any UI claiming other expressions would be dishonest — do not drive expression names not in this list.

## Physics

`VRMC_springBone` present → hair/clothing spring physics are defined in the asset and simulated by `@pixiv/three-vrm` automatically during `vrm.update(dt)` (already called every frame).

## Runtime verification (headless Chromium + SwiftShader)

- Loads without errors through `GLTFLoader` + `VRMLoaderPlugin` (fallback chain `hinaa.vrm` → `hinaa.vrm.bak`).
- Faces the camera after orientation fix (screenshot `docs/evidence/`/v3 series).
- No T-pose: relaxed idle applied via **normalized** bones (rest-pose-relative, portable across models). Previous raw-bone rotations with inverted signs put the hands on the face — fixed and re-verified visually.
- Camera framing is **measured**, not hard-coded: feet grounded at y=0, bounding box + `head`/`leftEye`/`chest` world positions produce eye/chest anchors; close-up, portrait and full modes derive from those anchors (`cameraForMode`).
- Blink runs on a randomized 2–6 s interval with a sinusoidal close/open.
- Mouth: **Basic energy lip sync** — `aa` viseme weight driven by playback jaw energy. It is *not* phoneme-accurate and must not be labeled as such; the asset has the full `aa/ih/ou/ee/oh` set, so proper viseme timing (e.g. from TTS timestamps) is the honest upgrade path. Mouth closes when jaw energy is zero (silence) and on interruption because energy collapses.
- Gaze/look-at: eye bones exist; procedural gaze is currently limited to subtle head motion — eye-bone gaze is available future work, supported by the asset.

## Model load failure path

If both model candidates fail (or WebGL context is lost), the stage renders an explicit fallback card ("3D model unavailable — place a VRoid export at `public/models/hinaa.vrm`") instead of a blank pane.
