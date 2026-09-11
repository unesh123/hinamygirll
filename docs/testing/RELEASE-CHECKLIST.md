# Release Verification Checklist

**Standard:** Sakura OS Production Quality Baseline  
**Audited:** September 3, 2026

---

## Pre-Flight Security Checks
- [x] Secret scan script (`scripts/secret_scan.py`) executed with zero findings.
- [x] No raw API keys, bearer tokens, or sensitive credential URLs in `.env.local`, logs, test files, or Git history.
- [x] Exposed Gamma key redacted and rotated with placeholder in `.env.local`.

## Automated Quality Verification
- [x] **TypeScript Compilation:** `pnpm --dir apps/web exec tsc --noEmit` exits with code 0.
- [x] **Frontend Unit & Integration Tests:** `pnpm --dir apps/web test --run` passes (36 test suites, 199 passed).
- [x] **Backend Pytest Suite:** `python -m pytest apps/api/tests -q` passes (100% test coverage).
- [x] **Backend Health Check:** `http://127.0.0.1:8000/health/live` returns HTTP 200 `{"status":"ok"}`.

## User Journey Verification
- [x] **Voice & VAD:** Bounded noise floor adaptation (`<= 0.022`) prevents lockup. Push-to-Talk button and spacebar hold successfully initiate and commit speech audio frames.
- [x] **Brain Fallback:** Rate-limited or unavailable CX brain automatically uses Gemini fallback with clear user notification.
- [x] **Natural Language Controls:** "Switch brain model" and related control phrases navigate to settings.
- [x] **Navigation:** Primary rail items (Talk, Chat, Projects, Creations, Memory, Studio, Settings) route to correct surfaces.
- [x] **Visual Consistency:** Image Studio and popover components (`/` and `@`) adhere to canonical Sakura OS light tokens.
