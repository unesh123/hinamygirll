# Hina local repair checkpoint — 2026-11-04

This is a bounded local repair, not a claim of completed architecture or human-real animation. Existing RAG, Freepik and provider implementation changes were preserved. No secrets, deployments, DNS or public listeners were changed.

## Changes

- `apps/api/hinaa_api/services.py`: silence watchdog sends a transport status event instead of synthetic spoken “One sec” text; handles simultaneous timer/token completion without discarding the token.
- `apps/api/tests/test_live_cross_session_api_e2e.py`: verifies waiting remains outside generated speech.
- `apps/web/src/components/ui/AvatarPresence.tsx`: lowers the original model's arms with smaller clavicle rotations, removes lateral walking drift and camera orbit, reduces hip sway/knee bend, adjusts gait cadence. Other model pose profiles remain intact.
- `apps/web/src/components/ui/AvatarPresence.test.tsx`: checks both wrists using forward kinematics and the shipped model's rest-bone offsets. This checks joint positions, not rendered mesh visibility.
- `apps/api/hinaa_api/providers/local_comfyui.py`: checks installed nodes/model dropdowns, accepts custom API workflow paths, avoids inherited HTTP proxies, verifies downloaded image bytes before registering paths.
- `apps/api/hinaa_api/config.py`, `apps/api/hinaa_api/tools/image_generate.py`: connect optional workflow paths to the existing provider.
- `apps/api/hinaa_api/main.py`: exposes workflow readiness and an API-prefixed local-service status alias.
- `apps/api/tests/test_comfyui_bridge_readiness.py`: six cases covering dependencies, custom workflow selection and downloaded image validation.
- `apps/web/src/design-system/chat/ModelSelectorV7.test.tsx`, `apps/web/src/design-system/modes/ModelsMode.test.tsx`: correct stale expectations to match the existing ability to retry a configured provider manually. No provider UI implementation changed.
- `scripts/check_comfyui_bridge.py`: read-only readiness CLI; explicit `--generate` optionally queues and validates one real image.
- `docs/workflows/hina-sdxl-starter-api.json`: seven-node SDXL starter with an intentional checkpoint placeholder.
- `docs/COMFYUI-SETUP-2026-11-04.md`: setup and reference-image instructions.

## Automated evidence

Run from the repository root unless a working directory is specified:

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_comfyui_bridge_readiness.py apps/api/tests/test_live_cross_session_api_e2e.py -o addopts= -q
```

Result: **13 passed**, one Google SDK deprecation warning. Provider calls and image bytes use test doubles; this is not a real ElevenLabs or ComfyUI render.

From `apps/web`:

```powershell
node node_modules/vitest/vitest.mjs run
node node_modules/typescript/bin/tsc -b
node node_modules/vite/bin/vite.js build
```

Results: **98 test files passed, 635 tests passed, 2 TODO**; TypeScript and production build passed. Large bundle warnings remain. Tests use jsdom, which does not provide actual audio playback or a rendered VRM performance measurement.

## Live local evidence and limits

- Local production frontend `http://127.0.0.1:5173/`: HTTP **200** after starting a persistent runner session.
- Backend `http://127.0.0.1:8000/health`: HTTP **200**. This proves HTTP availability only, not authenticated chat or all integrations.
- Read-only `scripts/check_comfyui_bridge.py`: exit **1**, `ready: false`, `serverReachable: false`. No real generation or downloadable image was verified. No model downloaded or API key installed.
- GPU inventory: NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB VRAM.
- Brave control selection timed out; native fallback did not return a usable observation. Visible hands, actual walking appearance, FPS, voice latency and authenticated live chat remain unverified.
- Animation remains procedural. Foot placement, motion capture quality and human realism are not established by the pose test.
- No new reasoning model was installed or benchmarked. Removing filler does not reduce upstream model inference time.
- Cloud image providers can still take precedence in the current generation pipeline. A dedicated local-renderer selection control has not been added.
- The public Vercel deployment was not changed or reverified. Local HTTP checks are not evidence of public ingress restoration.

## Local runner and rollback

Frontend runner command: `node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 5173 --strictPort` from `apps/web`.

Backend runner command: `apps/api/.venv/Scripts/python.exe -m uvicorn hinaa_api.main:app --app-dir apps/api --host 127.0.0.1 --port 8000` from the root. These are development runner sessions, not an installed always-on hosting service.

To roll back, review `git -c core.fsmonitor=false diff` and reverse only the hunks listed above, using interactive hunk selection. Remove newly added guide, starter, CLI and test files only after confirming nobody has edited them further. Stop only these local runner sessions with Ctrl+C. Do not reset whole files or discard unrelated working-tree changes. No environment-key rollback is required because none were changed.
