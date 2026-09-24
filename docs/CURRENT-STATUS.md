# HINAA current status

Updated: 2026-09-09 (Asia/Kathmandu)

Release decision: **Not ready for public launch yet.** The local app is substantially more reliable, but real provider credentials, deployment operations, voice acceptance, asset licensing, and performance work are still required.

## Verified in this pass

- Agent kernel now enforces per-run iteration, timeout, cost-unit, and skill allowlist limits; emits structured lifecycle audit events without exposing chain-of-thought; and reports failed, partial, and recovered runs distinctly.
- Tool dispatch now enforces registry argument contracts and per-tool timeouts, resolves owner identity from server-side auth, and rejects client-asserted policy-engine approvals.
- Capability discovery now reflects configured/allowed provider models and maps legacy `real` mode to its actual Gemini brain path.
- PDF generation preserves supplied content, escapes renderer input, and labels generated formatting/citation claims honestly instead of presenting fabricated benchmarks as research.
- Production web build TypeScript mismatch in VRM avatar expression input was repaired; `pnpm --dir apps/web build` now succeeds.
- Backend undefined-name lint regressions in memory, Gemini, and service modules were repaired; F821 lint is clean.

- Chat restores the dedicated view and active conversation after reload; messages remain in the selected conversation.
- Starting a new chat no longer clears the previous conversation through an old-controller race.
- Conversation storage is scoped by conversation id, avoiding the old global “ghost transcript”.
- The chat companion canvas renders, close-up framing keeps the face and shoulders visible, and switching the bundled VRM model preserves the selected camera framing.
- Custom `.vrm` imports upload to the API for durable browser URLs when the API is available; the object-URL fallback is clearly session-only.
- Avatar loading has a watchdog so a failed model cannot leave an infinite spinner or blank stage.
- Image Studio accepts one bounded PNG/JPEG/WebP reference, uploads it to ComfyUI, and wires it through LoadImage → ImageScale → VAEEncode → KSampler with controlled denoise. Text-only generation can use the cloud fallback; reference editing reports a clear error when local ComfyUI is offline. The request now includes the required user approval source.
- WorkMode transcript padding no longer produces the mixed shorthand/directional React style warning.
- Reference workflow regression tests cover upload ordering, pixel-to-sampler wiring, malformed/oversized input, offline references, and duplicate references.

## Evidence

- API health: `http://127.0.0.1:8000/health` returned `status: ok`, version `0.3.0`.
- Web server returned HTTP 200 on `http://127.0.0.1:5173/`.
- TypeScript: `pnpm exec tsc --noEmit` passed.
- Frontend unit suite: 45 files, 260 passed, 2 todo.
- Backend full suite: passed locally with the repository virtualenv.
- Browser smoke: avatar/chat flows passed on desktop Chromium and small Android (4/4 targeted Playwright tests).
- Avatar browser regression: Playwright `chat-avatar.spec.ts` and `talk-avatar.spec.ts` passed on desktop Chromium and small Android (4 passed); production preview build completed with the known large 3D chunk warning.
- Live browser check confirmed reload stayed in Chat, retained three messages, and rendered the avatar after loading.

## Remaining launch blockers

Real OpenAI/Anthropic/voice/Freepik credentials and quota handling; HTTPS and server-side secret storage; database/object-storage backup and restore; monitoring, rate limits, rollback, and abuse controls; native-speaker Nepali/Hindi/English microphone and playback acceptance; provider-timed lip-sync acceptance; mobile performance and 3D chunk optimization; full desktop-control permission and audit model; GitHub/MCP OAuth production review; asset provenance/licensing; and modernization of the skipped legacy e2e suite.

## Shareable handover

HINAA is a local-first React/Vite + Python API assistant with provider routing, tool authorization, conversation persistence, Image Studio, multilingual speech plumbing, and VRM avatar presentation. The highest-risk user-visible issues were addressed and regression-tested locally. It is not yet an honest “GPT/Jarvis equivalent” or public-production release: live provider keys, real-device voice tests, deployment security, licensed assets, and operational safeguards remain.
