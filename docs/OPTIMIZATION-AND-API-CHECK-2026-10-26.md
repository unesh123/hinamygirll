# Optimization and API check — 2026-10-26

Base revision: `05cc72b`. The worktree was clean at the start. No keys or environment files were printed, changed, or committed.

## Implemented

- Removed nested renderer-teardown components from both avatar engines. Their changing React identities could unmount and dispose the renderer during ordinary parent updates. React Three Fiber retains ownership of canvas cleanup.
- Fixed conditional hook ordering in VRM fallback/text-mode transitions and the waveform overlay.
- Paused WebGL rendering when the stage/tab is hidden. VRM visibility now uses an intersection observer with cleanup and resume behavior.
- Limited waveform React updates to approximately 30 samples/second and skipped negligible energy changes; hidden/overlay states avoid updates.
- Removed static imports that defeated the companion's lazy loading. The build now emits an independent ~47.65 KB avatar component chunk; the ineffective dynamic-import warning is gone. Other large dependencies still need future profiling.
- Restored fast-close/slower-open blink timing and corrected the model-label fallback.
- Added GMI Cloud as an explicitly selectable provider through the existing streaming adapter, with frontend/provider/settings contracts. Its dashboard URL is normalized to the documented inference endpoint, `https://api.gmi-serving.com/v1`.
- Added configuration aliases for existing Treg, Experimental Labs and You.com adapters. Configuration presence is not labeled as successful generation.

## Validation

- Full frontend suite: **93 files passed, 614 tests passed, 2 todo** after the performance/provider changes.
- Additional lifecycle/visibility tests: **2 passed**, including fallback → VRM → text → VRM transitions and hidden/offscreen pause/resume.
- Backend config/provider completeness/security tests: **53 passed**, one existing SDK deprecation warning.
- TypeScript and production build passed. Scoped diff whitespace check passed.
- Local preview started on `http://127.0.0.1:5173`; local FastAPI started on `http://127.0.0.1:8000`.
- Real HTTP checks: backend health 200 JSON (147 ms); preview 200 HTML (33 ms); preview-to-backend capabilities 200 JSON (1,843 ms). These are single observations, not latency percentiles or GPU benchmarks.
- Actual device FPS, frame-time percentiles, long-session thermals, and an authenticated production-browser session were **not measured**. No zero-lag guarantee or production deployment is claimed.

## Actual API results

| Service | Evidence | Status |
|---|---|---|
| XKIRO | Authenticated model list: 200, valid list | Discovery verified; generation not tested here |
| APMIX | Authenticated model list: 200, valid list | Discovery verified; generation not tested here |
| GMI Cloud | Configured URL was a dashboard; official inference model list returned 200 using the existing key | Adapter integrated |
| GMI generation | Bounded synthetic request returned **402**, no visible text | Account/quota/payment response blocks generation; not operational |
| PKay DeepSeek proxy | `/v1/models` returned 404; root is now “MOEI Gateway - Admin”; no current first-party inference docs established | Not integrated by guessing |
| NextProxy | Official docs identify a proxy-pool REST service, not an LLM; advertised `api.nextproxy.site` was unreachable from this machine | Infrastructure integration blocked |

An automated approval review rejected a combined PKay generation probe/local-launch command without a detailed reason. It did not run. The credential-bearing PKay probe was not retried. Separate local-only API and preview launches succeeded.

Sources: [GMI developer reference](https://www.gmicloud.ai/en/developers), [NextProxy API reference](https://nextproxy.site/api-docs), [NextProxy developer portal](https://nextproxy.site/developer). The implementation uses the user's existing credentials only; no public social-media keys were used.

The local services run current source/build. These changes have not been deployed to Vercel. Keep provider credentials server-side. GMI needs its 402 response resolved by its account owner before it can serve chat. PKay needs a confirmed current protocol/endpoint; NextProxy needs a reachable API host.
