# Hina response and speech latency repair — 2026-10-28

Scope: reduce avoidable preparation work and voice fallback delays. This is a local implementation checkpoint, not completion of the autonomous-agent architecture or a production deployment.

## Changes in this turn

- `apps/api/hinaa_api/services.py`: both typed and live turns now honor the existing FAST context route before historical/graph memory assembly. Detailed turns retain retrieval. Live prompt timing starts at entry, before context preparation.
- `apps/api/tests/test_turn_preparation_latency.py`: five offline tests cover typed/live greeting versus detailed-query retrieval and preparation timing using a controlled clock.
- `apps/web/src/features/audio/speechFallback.ts`: timed synthesis and audio-only fallback share one 15-second deadline and parent cancellation. An expired/cancelled attempt cannot start the second request. Actual fetch implementations must honor the supplied signal.
- `apps/web/src/features/audio/speechFallback.test.ts`: four tests cover successful fallback, shared signal, cancellation, timeout, and already-cancelled input.
- `apps/web/src/App.tsx`: connects that synthesis helper; removes the silent 90-word streamed-speech cutoff; structured-only responses use cleaned display text with spoken text as fallback instead of automatic truncation. Existing mute/stop and bounded prefetch remain.
- `apps/web/src/App.test.tsx`: changes the former 90-word-cap expectation to require the whole streamed answer exactly once, including after the final plan arrives.

The three avatar files already dirty at entry (`VRMAvatar.tsx`, `performanceSubstrate.ts`, `performanceSubstrate.test.ts`) retain the preceding playback-clock fix. No changes to RAG implementation, Freepik integration, credentials, provider configuration, or deployed infrastructure were made.

## Verification

Commands run from the repository root:

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_turn_preparation_latency.py apps/api/tests/test_context_compiler_b2.py apps/api/tests/test_context_compiler_b21.py apps/api/tests/test_fast_path.py apps/api/tests/test_live_generation_window.py -o addopts= -q
pnpm --dir apps/web test
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
git diff --check
```

- Backend: **77 passed**, one Google SDK deprecation warning. This is a focused suite, not the entire backend suite.
- Frontend final full run: **95 files passed; 622 tests passed; 2 todo**. Test environment emits existing unimplemented browser media/canvas/scroll and React warnings. These are mocked DOM checks, not real GPU or speaker verification.
- TypeScript and production build: passed. Large bundle warnings remain, including Mermaid, ELK, React Three and the main bundle.
- Diff whitespace check: passed; Git reports an informational LF/CRLF conversion warning for services.py.
- The initial full frontend run failed its obsolete 90-word-cap expectation. After changing that expectation to the requested complete speech behavior, the App suite and final full suite passed.

## Local runtime evidence

Started hidden, bound to loopback only:

- API: `python -m uvicorn hinaa_api.main:app --app-dir apps/api --host 127.0.0.1 --port 8000` (server PID 28928 at verification).
- Built frontend: `node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 5173 --strictPort` from apps/web (launcher PID 38640).
- Logs: `.runtime/latency-repair/`.

Actual local HTTP observations, one request each:

| Endpoint | Status | Elapsed |
|---|---|---|
| `http://127.0.0.1:8000/health/live` | 200 JSON | 374 ms |
| `http://127.0.0.1:5173/` | 200 HTML | 182 ms |
| `http://127.0.0.1:5173/health/live` | 200 JSON | 202 ms |

These show local availability and the health proxy only. They do not prove authenticated chat, public ingress, AI response quality, model time to first token, live ElevenLabs output, audio latency, or 3D frame rate. No external paid inference was used for these tests.

## Remaining verification and limitations

Measure authenticated first text, first audible speech, interruption, and desktop/mobile frame times together. The 15-second deadline is an upper waiting budget for a phrase's neural synthesis attempts, not a claim of fast first audio. Full speech can consume more TTS quota than the previous truncated behavior; mute and interruption remain available. Asset optimization and authored facial/body motion remain separate unfinished work. No promise of human-equivalent behavior or unrestricted reliable autonomy is established by this patch.

## Rollback limited to this turn

Review the diff before reversing it. Remove only the FAST guards and timer relocation in services.py; reverse only the speech helper wiring and speech-length changes in App.tsx and the corresponding App test expectation; remove the new latency test and the two new speechFallback files if unused. Preserve the three pre-existing avatar diffs and every unrelated change. Do not reset whole files. Stop only the local processes identified above if the local runners are no longer needed, checking their command lines first because PIDs can be reused.
