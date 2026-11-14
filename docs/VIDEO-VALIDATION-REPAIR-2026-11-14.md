# Video artifact validation repair — November 14, 2026

Preserved the pending Coarena repairs and status report. No cloud generation, public deployment, credential edits or commits were performed.

## Problem and repair

Provider checks and asset registration previously accepted padded bytes carrying an `ftyp` header as video. The provider unit fixtures still simulate network output; those tests are not proof of playable media.

Added `creative/assets/video_validation.py` and wired it into `CreativeAssetManager.store_asset`. Before any video is written or registered, ffprobe must find a valid non-cover-art video stream and ffmpeg must decode it. Metadata comes from the actual file. Missing validation tools, malformed/truncated data, invalid duration/dimensions, decode errors and timeout fail closed.

Validation limits: 128 MiB input, at most 3840×2160 pixels and 300 seconds, 15-second probe timeout, 45-second decode timeout, two decoder threads and file/pipe protocols only. These are bounded implementation limits, not support for arbitrary media sizes. Temporary validation files are cleaned up.

Asset storage calls in `creative/jobs/service.py`, `creative/lyric_video/jobs.py` and `routers/creative_router.py` now run in worker threads so video validation does not synchronously block the API event loop. Cancellation cannot forcibly stop a Python worker thread; validation remains time-bounded, and hard subprocess cancellation/orphan cleanup is a remaining lifecycle gate.

Downloads check the stored SHA-256 before serving. Changed files return 409; missing files return 404. HTTP download tests use the actual route in a local TestClient, not a deployed browser.

## Evidence

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_video_asset_validation.py apps/api/tests/creative/test_c09_suite.py apps/api/tests/test_lyric_video.py -o addopts= -q
```

86 passed, 3 deprecation warnings, 32.14 seconds. After the final download-hash change, the focused `test_video_asset_validation.py` suite passed again: 6 passed in 0.82 seconds. `git diff --check` passed.

New tests cover fake headers, missing tools, real encode/probe/decode/storage, truncation, decoder timeout, exact download bytes/MIME/ETag, different-tenant lookup denial, missing files and altered-file rejection. Real media encoding and decoding use installed FFmpeg; timeout is injected. This does not prove authenticated tenant isolation across the complete app.

Standalone local sample: `.runtime/video-acceptance-2026-11-14/verified-local-clip.mp4`; receipt: `receipt.json` alongside it. Synthetic blue clip, H.264, 320×180, 24 FPS, 2 seconds, 2935 bytes. SHA-256: `bd1f24d183eb58dbb3b197662c4524bbeca426fcd527054d6488923fdb3eec52`. It is deliberately not represented as AI-generated footage.

## Remaining blockers

- Neither Hugging Face nor fal.ai video credential is configured in resolved settings. Real cloud request → generated output → browser download remains unverified.
- Asset metadata currently lives in an in-process dictionary. Durable registry recovery after API restart remains unfinished.
- Creative routes accept tenant/user selectors; full server-derived ownership enforcement must be audited before public release.
- Cancellation during threaded registration, artifact cleanup, download error UI, mobile/desktop visuals and avatar/voice performance remain acceptance work.
- This milestone does not establish that every feature is complete.

## Rollback

Reverse only the video-validation import/call and metadata additions, the three threaded storage-call changes, and download-integrity hunk. Remove the new validator/test/report only if no later edits depend on them. Preserve unrelated provider changes. Refresh the owned API afterward. Do not reset whole files or erase unrelated runtime data.
