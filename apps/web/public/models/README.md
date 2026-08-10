# VRM model slot

The app ships a real 3D anime girl at **`hinaa.vrm`** (bundled) and auto-loads it —
no code changes needed. Drop in your own VRoid Studio export over it any time.

## What's bundled now

- **`hinaa.vrm`** — owner-selected VRoid girl **“Libby_free”** (21.6 MB, VRM
  0.x, by creator `rurune`), downloaded 2026-08-09 and placed at
  `apps/web/public/models/hinaa.vrm`. Embedded terms: allowed for everyone's
  use, personal use, modification allowed; **commercial use disallowed** —
  keep her for personal/local use, do not ship commercially without a
  re-license.
  SHA-256: `00d914951da30714aad2d5e63da1fb60816b407a9b630f56b11a3ef955933d9d`
  See `docs/ASSET_LICENSES.md` for the full licence row.
- Previous bundled model backed up at `hinaa.vrm.bak` (19 MB, MIT anime-girl,
  SHA-256 `ef55df5369e197e8b7f696ef853f566be178f075a4887bb264da1b33be6f8ea0`).

## How to replace it with your own model

1. Export your character from [VRoid Studio](https://vroid.com/studio) as a
   `.vrm` file (typically 5–20 MB).
2. Save it over: `apps/web/public/models/hinaa.vrm`
3. Restart the dev server (Vite serves new public files on restart).
4. Open the app — the 3D girl renders full-screen with lip-sync, blink, gaze,
   expressions, and gestures wired to her emotions.

> Hiro is a separate slot if you have a male model: `hiro.vrm`

## What happens if the file is missing

The app falls back to the pixiv/three-vrm sample model (`VRM1_Constraint_Twist_Sample.vrm`)
so the 3D pipeline always works during development, then to the 2D procedural
avatar if the network sample can't load.

## Licensing

- Bundled `hinaa.vrm`: **Libby_free** by `rurune` — embedded VRM terms:
  allowed to all users, personal/non-commercial use, modification allowed,
  commercial use **disallowed**. Re-verify the VRoid Hub licence page
  (`rurunerune.booth.pm`) before any commercial release. Source + checksum
  recorded in `docs/ASSET_LICENSES.md`.
- Previous bundled model (`hinaa.vrm.bak`): MIT-licensed upstream repo.
- Your own VRoid Studio export is covered by the [VRoid Studio licence](https://vroid.com/en/studio/terms)
  for personal use (check the version you exported with).
- Record the exact licence, provenance, and checksum in
  `docs/ASSET_LICENSES.md` before shipping — see the existing entries there.
