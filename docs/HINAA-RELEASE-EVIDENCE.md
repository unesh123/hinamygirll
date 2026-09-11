# HINAA release evidence

Updated: 2026-09-09 18:40 +05:45

Release decision: **NOT READY for public multi-user launch**.

| Gate | Current evidence | State |
| --- | --- | --- |
| Spoken fallback | Focused spoken-text fallback tests repaired earlier; full frontend suite now passes 198 tests | Verified for local fallback |
| Frontend type/build | `pnpm exec tsc --noEmit` passed; Playwright webServer production build passed | Verified |
| Frontend unit suite | `pnpm test` passed: 45 files, 260 tests, 2 todo | Verified |
| Frontend lint | `pnpm lint` exits 0; historical warnings remain | Partial |
| Browser e2e | Avatar/chat smoke passed on desktop Chromium and small Android (4/4 targeted tests); the broader legacy suite still contains skipped specs | Partial |
| Backend suite | `.venv\Scripts\python.exe -m pytest -q` passed locally with the repository virtualenv; only upstream dependency deprecation warnings remain | Verified |
| Backend critical lint | `.venv\Scripts\python.exe -m ruff check --select F821 hinaa_api tests` passed | Verified |
| Agent kernel guardrails | Timeout, cost budget, skill allowlist, truthful missing-executor failure, retry audit history, terminal status, and explicit artifact extraction covered by `test_agent_kernel.py` | Verified locally |
| Tool execution boundary | Registry argument validation, per-tool timeout, server-side owner identity, and rejection of client policy-engine approval covered by `test_tool_dispatch.py` | Verified locally |
| Capability catalog | Active/allowed provider models and mode-specific defaults covered by `test_capabilities.py` | Verified locally |
| PDF generation | Supplied content preservation and no-canned-claim regression covered by `test_pdf_generate.py` | Verified locally |
| Backend full Ruff style | Full Ruff style run reports historical import/line-length/unused debt | Pending |
| Nepali/Hindi/English | Language policy now flows through settings, contracts, prompts, speech fallback, realtime, and Azure hints | Implemented locally |
| Actual live speech | No current real-device three-language microphone/audio acceptance recording | Pending |
| Avatar | Full-body VRM Talk mode visually inspected live; Playwright regression verifies canvas/caption layout across desktop/mobile | Partial |
| Lip sync | Text/audio-driven viseme path exists; provider-timed phoneme-perfect lip sync is not proven | Pending |
| Tool authorization | Sensitive tools require real user approval source, not standing consent/autonomy | Improved |
| Owner isolation | Artifact lookup and image polling now use resolved server-side identity | Improved |
| Clerk auth | Server-side Clerk JWT verification added and tested; frontend Clerk gate added | Improved |
| Research quality | Adapters exist; sourced multi-step outcome evaluation still required | Pending |
| Freepik | Key expected from owner; server-side integration not live-verified | Pending |
| Asset rights | Existing repository requires provenance/license review | Blocking for distribution |
| Production operations | Backup/restore, load, rollback, quota, observability, and tenant tests required | Pending |

Never overwrite failures with a completion claim. Distinguish local mocks, browser checks, paid-provider checks, and real-device acceptance.
