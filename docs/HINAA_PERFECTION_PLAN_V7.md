# HINAA Perfection Plan V7 — Make Hina Highly Perfect & Complete

**Date:** 2026-09-15 · **Branch:** `feat/hinaa-ui-polish` · **Live:** Vercel (web) + Render (API)
**Purpose:** The single execution plan for Antigravity (currently working in this tree) to take Hina from "RC1-strong" to highly perfect and complete — across brain/models, voice, avatar, UX, tools, memory, media, and production safety.
**Rule:** Nothing here is generic. Every task names real files, real commands, and a hard acceptance gate.

---

## 1. CURRENT TRUTH (evidence, not vibes)

### 1.1 What is DONE (verified in tree)
- **24/24 product surfaces PASS** per `docs/HINAA_PRODUCT_V6_FINAL_ACCEPTANCE.md` (AppShell, Talk/Work/Operate modes, Composer, Sidebar, TopBar, Dock, Context Chips, Galleries, Tool Cards, Mobile, Loading/Error/Empty states, A11y, Keyboard, Performance).
- **Test baseline claimed:** 878 pytest + 313 vitest green, `tsc` clean, Vite build clean.
- **Long-generation architecture exists:** `GenerationOrchestrator` + structural continuation triggers + seam dedup + consistency pass (`apps/api/hinaa_api/generation/`).
- **B1 already landed:** `apps/web/src/contracts/assistantTurnPlan.ts` now caps `displayText` 150,000 / `spokenText` 8,000 WITH a salvage normalizer — the old 8k truncation killer is gone.
- **B2/B3 appear landed:** `apps/api/hinaa_api/providers/agent_router.py` now wires `GenerationOrchestrator` + `AdaptiveStreamDecoder` (the repeat-line + no-continuation defects from `HINAA_ADVANCEMENT_REPORT.md`).
- **Phase A (doc 78) shipped:** Magnific FLUX contract, image self-diagnostic, query cleaning, slash commands, structured answer modes, voice distiller.
- **Deployment wiring:** `vercel.json` rewrites `/api/*`, `/v1/*`, `/health` → `https://hinamygirl-api.onrender.com`.

### 1.2 What is IN-FLIGHT (uncommitted — land first!)
`git status` shows 5 modified files NOT committed:
1. `config.py` — CORS allowlist adds `https://hinaa-workspace.vercel.app`.
2. `main.py` — CORS regex `https://.*\.vercel\.app`, `allow_headers=*`, NEW `GET /v1/capabilities` (+`/api` alias), NEW `POST /api/v1/conversations/turns:stream` alias.
3. `backendConversationProvider.ts` — explicit `VITE_HINAA_API_BASE_URL`, no silent mock fallback (throws `BACKEND_UNAVAILABLE`).
4. `mockConversationProvider.ts` — mock FORBIDDEN in PROD.
5. `useCompanionController.ts` — PROD defaults to `claude` backend, never mock.
- **Risk:** Antigravity is editing these exact seams. DO NOT start new work until §3 Phase 0 lands this.

### 1.3 Known gaps / suspects (must verify, not assume)
- G1. `/v1/capabilities` advertises `deepseek-chat`, but `providers/` has NO `deepseek.py` — confirm DeepSeek routes via agent-router-openai `base_url` or add a real provider. Hardcoded Gemini model list in the endpoint (`gemini-2.5-pro/…`) must derive from settings.
- G2. B2/B3 fixes exist in code but need PROOF: escape-split test, orchestrator test for agent-router, 30k-char client test (§5 of advancement report).
- G3. `planned_sections` still may not reach orchestrators (dead-code trigger) — verify.
- G4. `llm_stream_idle_timeout_seconds` in config but providers may still hard-code 300s httpx timeout — verify.
- G5. Mock/cross-session spoken override (`services.py` ~2690) may still bypass `plan_voice_response` — verify + test.
- G6. VRM licensing: root `.vrm` files + `ASSET_LICENSES.md` quarantine unresolved — public launch blocker.
- G7. Capability backlog `HINAA-CAPABILITY-BACKLOG.md`: all 120 boxes unchecked — use as the final sign-off sheet.
- G8. No SSE keepalive during multi-minute streams (proxies can kill idle connections).

---

## 2. TARGET DEFINITION — "HIGHLY PERFECT & COMPLETE" MEANS

| Pillar | Perfect = |
|---|---|
| 🧠 Brain & Models | Every provider path (claude, agent-router, gemini, groq, openai, mock-dev) streams long answers 2–4+ min with zero repeats, zero truncation, all requested sections, + 1 warm spoken summary. `/v1/capabilities` truthfully reflects configured models only. |
| 🎙️ Voice | Nepali/Hindi/English STT+TTS, Simran ElevenLabs voice default, barge-in, echo guard, lip-sync visemes incl. Devanagari, hands-free loop stable. |
| 🧍 Avatar | 5 bundled VRM models switch cleanly, watchdog never leaves blank stage, idle sway + gestures, expression follows emotion plan, 60fps desktop / degraded-mobile tiers, licensed. |
| 💬 Chat UX | Streaming markdown, stop/retry/regenerate/edit-resend, history search, conversation branches, context chips, artifacts, goals, empty/loading/error states everywhere. |
| 🛠️ Tools & Autonomy | 49 tools real (web, media, docs, GitHub, system), approvals for dangerous ops, durable tasks with checkpoints/steer/rollback. |
| 🖼️ Media | Magnific FLUX gen + upscale + reference edit with self-diagnostic strip; image search relevance; PDF export with Unicode font; presentations. |
| 🧠 Memory | Explicit memory candidates with confirmation, cross-session continuity, privacy delete, per-user scoping. |
| 🛡️ Production | No localhost assumptions, no mock in PROD, CORS locked, secrets server-side, rate limits, health/load-balancer ready, backups, rollback, monitoring, abuse controls. |

---

## 3. PHASE 0 — LAND & STABILIZE (do TODAY, before anything else)

**Owner:** Antigravity · **Effort:** 0.5 session · **Risk:** LOW

- [ ] **P0-1. Commit or revert the 5 dirty files.** Run `git diff` review, then commit as `fix(prod): vercel CORS, capabilities endpoint, no-mock-in-prod` — or split: (a) backend CORS+capabilities, (b) web no-mock. Never leave PROD behavior uncommitted.
- [ ] **P0-2. Fix G1 immediately in the same commit:**
  - `main.py::get_capabilities` — replace hardcoded `["gemini-2.5-pro", "gemini-2.5-flash", "gemini-1.5-pro"]` with `active_settings` values; only list `deepseek-chat` when `has_deepseek` is true AND routing actually supports it (else drop it from the advertised list until a provider exists).
  - Verify `GET /v1/capabilities` and `GET /api/v1/capabilities` return 200 with no credential leakage.
- [ ] **P0-3. Prove the live chain end-to-end on the DEPLOYED URLs:**
  ```powershell
  curl https://hinamygirl-api.onrender.com/health
  curl https://hinamygirl-api.onrender.com/v1/capabilities
  curl -N -X POST https://hinamygirl-api.onrender.com/v1/conversations/turns:stream `
    -H "Content-Type: application/json" -d '{"text":"Say hi in one line","companionId":"hinaa"}'
  ```
  Then open the Vercel site, send one message, confirm the reply comes from the backend (check `resolvedProvider`, NOT mock).
- [ ] **P0-4. Gate:** `git status` clean, deployed smoke passes, `VITE_HINAA_API_BASE_URL` set in Vercel env.

---
## 4. PHASE 1 — BRAIN & MODELS PERFECTION (the core ask)

**Owner:** Antigravity · **Effort:** 2 sessions · **Risk:** MEDIUM
**Files:** `providers/agent_router.py`, `openai_llm.py`, `gemini.py`, `groq.py`, `generation/*`, `services.py`, `contracts/assistantTurnPlan.ts`

- [ ] **P1-1. Prove B1/B2/B3 with tests (advancement report section 7):**
  - Backend: orchestrator continuation test for agent-router (fake two-segment stream, MAX_TOKENS finish reasons); escape-split robustness test (split escapes across chunks, expect no dup).
  - Web: `assistantTurnPlan.test.ts` — 30,000-char displayText must parse and survive; streaming suppression still hides fenced-JSON fragments.
  - Run backend pytest + web vitest, both green.
- [ ] **P1-2. Kill G3/G4/G5:**
  - Pass `planned_sections` (from user text/mode) into ALL orchestrators.
  - Wire `llm_stream_idle_timeout_seconds` as httpx per-read timeout in every streaming provider (no hard-coded 300s).
  - Audit `_apply_response_quality_guard` on EVERY return path incl. fallbacks; enforce `plan_voice_response()` after the mock/cross-session spoken override; add summary-channel tests.
- [ ] **P1-3. SSE keepalive:** emit ping comments every ~15s during long streams so Vercel/Render/proxies don't kill multi-minute generations.
- [ ] **P1-4. Single source of budgets:** client/server caps from one shared constant or a `/config` endpoint the web reads at boot.
- [ ] **P1-5. Manual smoke per provider mode** (claude, agent-router, gemini, groq, openai, mock-dev): a ~5,000-word report with explicit sections must stream continuously with zero dup lines, all sections present, spoken = 1 warm summary, no truncation.
- [ ] **P1-6. Gate:** all new tests green; smoke passes on all 6 modes; spoken-summary invariant holds.

---


> **P0-5 (added on review).** `useCapabilities.ts` fallback defaults claim `configured: true` for Claude/Gemini models even when the server is unreachable. On fetch failure the UI must show `backendConnected: false` and mark every provider/model unconfigured instead of inheriting the optimistic defaults. Same fix in `main.py::get_capabilities`: only advertise DeepSeek when routing truly supports it.
## 5. PHASE 2 — VOICE, AVATAR & MODELS (she must feel alive)

**Owner:** Antigravity · **Effort:** 2–3 sessions · **Risk:** MEDIUM

**Voice** (`providers/elevenlabs.py`, `fish_audio.py`, `deepgram_voice.py`, `azure_speech.py`, `realtime.py`, `voice_performance.py`, web `features/voice/*` + `features/avatar/*`):
- [ ] **P2-1.** Simran voice default for Hinaa, Hiro mapped to its own voice; server-side keys only, never VITE secrets.
- [ ] **P2-2.** Live-mode TTS concision parity (doc 78 Phase D.2): realtime paths speak the distilled summary, never the full document.
- [ ] **P2-3.** Barge-in ducking tests; PlaybackLeakGuard echo protection on real devices; Devanagari viseme lip-sync acceptance.
- [ ] **P2-4.** Native-speaker acceptance: Nepali/Hindi/English mic + playback on desktop + Android; record in `docs/68-real-voice-evaluation.md`.

**Avatar and 3D models** (`apps/web/public/*.vrm`, `features/avatar/VRMAvatar.tsx`, `TalkMode.tsx`, `avatar_assets.py`, `vmc_bridge.py`):
- [ ] **P2-5.** All 5 bundled VRM switch cleanly with camera framing preserved; watchdog kills infinite spinners; idleSway on every model; expression/gesture follows the emotion plan.
- [ ] **P2-6.** Motion pack (doc 78 D.1): idle weight-shift + gesture .vrma clips via three-vrm-animation from `public/animations`; NO procedural walking (ships broken — rejected).
- [ ] **P2-7.** Performance tiers: 60fps desktop, auto-degrade on mobile (FPS monitor lowers pixel ratio/shadows); 3D chunk split for fast first paint.
- [ ] **P2-8.** Licensing gate (launch blocker): every shippable .vrm gets provenance + redistribution terms in `docs/ASSET_LICENSES.md`; unlicensed files leave `public/` and the switcher.
- [ ] **P2-9. Gate:** voice + avatar acceptance signed on 2 real devices; licenses recorded.

---

## 6. PHASE 3 — CHAT, TOOLS, MEDIA, MEMORY (complete product)

**Owner:** Antigravity · **Effort:** 2–3 sessions · **Risk:** LOW–MEDIUM

- [ ] **P3-1. Conversation completeness** (backlog H001–H010): stop/retry/regenerate/edit-resend/branch/history-search — success path, failure behavior, permission boundary each.
- [ ] **P3-2. Tools and autonomy:** /v1/tools 49 tools real; dangerous tools need approval UI; durable tasks (checkpoints, steer, rollback) verified; workspace-jail + patch-as-proposal + terminal-runner ONLY per doc 78 Phase C safety design. Self-heal auto-loops stay DEFERRED.
- [ ] **P3-3. Media:** Magnific FLUX gen/upscale/reference-edit green with diagnostic strip; image-search relevance regression test; Unicode TTF bundled in `assets/fonts/` for Devanagari PDFs; Export-answer on all assistant messages; presentations verified or honestly degraded.
- [ ] **P3-4. Memory and privacy:** memory candidates need confirmation; cross-session continuity guard; per-user scoping; privacy delete works; no ghost transcripts.
- [ ] **P3-5. Multilingual:** Nepali/Hindi/English + code-mixing, locale-aware speech, technical-term preservation, native-script rendering (H011–H020).
- [ ] **P3-6. Gate:** backlog H001–H100 spot-checked green; tool approval + rollback demoed.

---

## 7. PHASE 4 — PRODUCTION HARDENING AND LAUNCH

**Owner:** Antigravity + owner (keys/approvals) · **Effort:** 1–2 sessions · **Risk:** LOW

- [ ] **P4-1. Eradicate localhost assumptions:** re-run the RC1 section-2 checklist (no 127.0.0.1/localhost:8000 in web prod paths; desktop bridges badged DESKTOP_BRIDGE/LOCAL_ONLY).
- [ ] **P4-2. Secrets and auth:** server-side secret store only; VITE carries zero secrets; auth + tenant isolation verified; rate limits/quotas/budgets enforced; audit/tracing on.
- [ ] **P4-3. Data safety:** Postgres/pgvector backup+restore drilled; object storage private; migrations green; staging rollback rehearsed (docs 35–38 runbooks).
- [ ] **P4-4. Observability:** health aliases for load balancers; latency/usage metrics; error-code mapping to UI recovery actions.
- [ ] **P4-5. CI gates:** mobile check + Playwright + pytest + vitest + tsc wired in CI; legacy skipped e2e modernized or explicitly retired.
- [ ] **P4-6. Final sign-off:** all 120 backlog boxes (H001–H120) verified; update `docs/CURRENT-STATUS.md` to Ready only with evidence links.
- [ ] **P4-7. Gate:** production truth audit v2 (repeat RC1 24-surface matrix on DEPLOYED URLs, not localhost).

---

## 8. ANTIGRAVITY COORDINATION (avoid stepping on each other)

1. Single-writer rule: Antigravity owns implementation; this plan file is the contract — tick checkboxes HERE as work lands.
2. Commit discipline: small conventional commits; never mix CORS/config changes with feature work; push the Phase 0 commit FIRST.
3. No blind inheritance: every PASS needs the command + output in the commit/PR body (RC1 truth-audit standard).
4. Don't regress: canonical files only (ComposerV6, SettingsV6, canonical sidebar/nav). Retired legacy stays deleted.
5. Cost guard: mock mode for iteration; paid-provider tests only with explicit capped approval.

---

## 9. VERIFICATION PLAYBOOK (run after every phase)

```powershell
cd apps/web; pnpm exec tsc --noEmit; pnpm test; pnpm build
cd apps/api; python -m pytest tests -q
curl https://hinamygirl-api.onrender.com/health
curl https://hinamygirl-api.onrender.com/v1/capabilities
python scripts/validate_blueprint.py
```

Done = Phase 0–4 gates green + 120/120 backlog verified + truth audit v2 on deployed URLs + CURRENT-STATUS.md Ready with evidence.

---

## 10. PRIORITY ORDER (if time is short)

1. Phase 0 (land + smoke) — 0.5 session.
2. Phase 1 P1-1/P1-2 (repeat-line + truncation kill).
3. Phase 2 P2-1/P2-5 (voice default + avatar switching).
4. Phase 4 P4-1/P4-2 (no-mock-in-prod, secrets).
5. Everything else in order.
