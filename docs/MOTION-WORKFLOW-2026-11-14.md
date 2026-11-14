# Local code-driven motion workflow

Implemented November 14, 2026, preserving all existing uncommitted provider and video-validation repairs.

## What works

`creative/motion.py` defines editable typed scenes with titles, subtitles, labels, duration, accent and orbit/bars/steps layouts. Rendering uses deterministic Pillow drawing, eased entrances, scene fades and a timeline indicator. It executes no model-supplied Python/JavaScript and requires no video API. The initial style is a restrained explainer template, not a general After Effects replacement.

`CreativeJobSpec.motion_scenes` feeds the existing `TIMELINE_EXPORT` path. The registered `create_motion_video` tool accepts a scene plan, awaits the creative job, and returns success/download metadata only after validation and registration. Tool cancellation requests job cancellation. Existing worker-thread cancellation limitations remain.

`scripts/render_motion.py` creates an MP4, editable source JSON, HTML video preview, scene PNG previews and a measured media receipt. Example source: `examples/motion/hina-introduction.json`.

```powershell
apps/api/.venv/Scripts/python.exe scripts/render_motion.py examples/motion/hina-introduction.json .runtime/hina-motion-demo
```

Bounds: at most 8 scenes, 30 seconds, 900 frames, 720p pixel budget and even dimensions. The tool currently renders at 960×540/24 FPS. Local FFmpeg and ffprobe are required. Rendering/model planning still consume local compute or existing model quota; no claim of universally free cloud services is made.

## Verified output

- Real local render: 12 seconds, 960×540, 24 FPS, H.264.
- Visually inspected scene 2 PNG for layout and legibility; full browser playback was not inspected.
- Direct invocation of the registered tool handler completed job `job-cr-a52cd48b` and registered asset `asset-eef3471d6a30`.
- Actual download route in local FastAPI TestClient returned HTTP 200, 62,067 bytes, SHA-256 `c63b826a323242069b5c9ca010000fb9cb9f1942553c242aa3c3dcfad86a6dae`.
- Receipt: `.runtime/hina-motion-demo/tool-receipt.json`. This is local handler-to-worker-to-artifact evidence, not a live chat/UI or cloud generation test. The test process's in-memory asset URL is not a durable live-server link; use the standalone `motion.mp4` for viewing.
- 73 tests passed across `test_motion_scenes.py`, `test_video_asset_validation.py` and `creative/test_c09_suite.py`; one Google SDK deprecation warning. Deterministic motion, changing frames, schema rejection and resource budgets covered. `git diff --check` passed.

## Still required

Natural-language tool selection and prompt-to-storyboard quality must be verified through Hina's actual chat. A visual scene editor, soundtrack/voice synchronization, charts driven by actual data, reference matching, arbitrary imported assets and richer layouts are not implemented by this milestone. Long unbroken text and unusually dense scenes need further typography handling. Existing asset persistence and tenant-ownership acceptance gaps remain; do not publish based on local demo success.

No frontend redesign, public deployment or remote repository mutation was performed. Local runner was restarted after discovering it was no longer listening during the final runtime check.

Rollback only the new motion module/tool/script/example/test, their imports, the `motion_scenes` field and timeline scene-rendering branch. Preserve earlier video-validation, download-integrity and provider repairs. Do not reset whole files.
