# HINAA LIVE UI & RUNTIME FORENSIC AUDIT V5
**Target URL**: https://hinaa-workspace.vercel.app/  
**Audit Date**: September 15, 2026  
**Auditor**: Principal Product Engineer & AI Systems Architect (Antigravity)  
**Deployment**: Vercel Production (`hinaa-workspace-1tzqclcrt-uneshs-projects.vercel.app`)

---

## 1. Executive Forensic Summary

A live forensic audit was performed directly against the deployed production target `https://hinaa-workspace.vercel.app/` using headless and headful Chrome DevTools automation across 7 standard viewports (Desktop, Tablet, Mobile).

### Key Findings
1. **P0 - Backend API Proxy 404**: `vercel.json` rewrites target `https://hinamygirl-api.onrender.com` which is not provisioned or active. All runtime endpoints (`/api/v1/conversations/turns:stream`, `/api/v1/providers`, `/api/v1/commands`, `/api/v1/privacy/memories`, `/v1/tasks`, `/v1/tools`) return HTTP 404. When a user submits a message, the UI catches the 404 and displays: *"Execution paused safely. Backend request failed (404) Try another brain model or text mode."*
2. **P0 - Aggressive Polling on Failed Endpoint**: The client continuously polls `/api/v1/providers` every ~30 seconds, generating dozens of 404 errors in the console and network log.
3. **P1 - Composer V5 Discrepancies**:
   - The composer lacks first-class **Context Chips** (`[Project: HINAA ×]`, `[Repo: frontend ×]`, `[IMG_24 ×]`).
   - The toolbar uses horizontal mode pills (`Chat`, `Research`, `Create`, `Code`, `Goal`) rather than the frontier unified layout: `+ | Auto ▾ | Goal Mode | Create ▾ | Agent Cluster | 🎙 | ↑`.
   - The `+` menu has only 6 items and overlaps the composer input box instead of anchoring cleanly above. It lacks options for Projects, Repositories, Video, Audio, Artifacts, Web Research, Presentations, Spreadsheets, and Integrations.
   - Goal Mode behaves as a local prompt prefix rather than creating/resuming a durable `ActiveGoal` with criteria, constraints, and reload persistence.
   - Agent Cluster control is absent from the primary composer bar.
4. **P1 - Memory Panel Viewport Clipping**: Clicking "Memory" on the left nav rail opens a sheet that is clipped at the bottom of the screen (90% offscreen on desktop 1920x1080).
5. **P2 - VRM Model CDN & Context Recovery**: The 3D avatar successfully loads from GitHub raw CDN (`/models/hinaa.vrm` -> HTTP 200/304). On rapid viewport resize, WebGL context loss is handled and recovered, but THREE.Clock deprecation warnings are logged.
6. **P2 - Accessibility & Focus**: Several form elements and buttons lack explicit `id`, `name`, or `aria-label` attributes. Modals require complete focus trap and Escape listener cleanup.

---

## 2. Viewport Evidence Matrix

| Viewport | Category | Screenshot Evidence | Observations |
|---|---|---|---|
| 1920x1080 | Desktop Large | `docs/screenshots/v5_audit/before_desktop_1920x1080.png` | 3D avatar docked right, inspiration cards centered, composer at bottom. Clean typography. |
| 1440x900 | Desktop Standard | `docs/screenshots/v5_audit/before_desktop_1440x900.png` | Proper proportions, no clipping on main cards. |
| 1280x720 | Desktop Compact | `docs/screenshots/v5_audit/before_desktop_1280x720.png` | Compact spacing preserved. Topbar search bar compresses gracefully. |
| 1024x768 | Tablet Landscape | `docs/screenshots/v5_audit/before_tablet_1024x768.png` | Companion dock shifts to compact width; composer maintains full usability. |
| 430x932 | Mobile Large (iPhone 14 Pro Max) | `docs/screenshots/v5_audit/before_mobile_430x932.png` | Mobile tab switcher (`💬 Chat` / `🌸 3D Avatar`) active. Avatar hidden in chat tab. |
| 390x844 | Mobile Standard (iPhone 13/14) | `docs/screenshots/v5_audit/before_mobile_390x844.png` | Vertical stack clean. Composer touch targets accessible. |
| 360x800 | Mobile Compact (Android standard) | `docs/screenshots/v5_audit/before_mobile_360x800.png` | Minimum width handled without horizontal overflow. |

---

## 3. Surface & Mode Forensic Inventory

### Work Mode (Chat)
- **TopBar**: HINAA Workspace pill, Talk/Work/Operate tabs, Search button (Cmd+K), Provider status pill (`cx/gpt-5.6-sol · Ready`). PASS.
- **Empty State**: Centered "Hello / What would you like to work on?" with 4 action tiles: Research, Create, Continue work, Talk to HINAA.
- **Composer**: Textarea with send button, voice button, `+` button, mode pills.
- **Companion Dock**: Hinaa Classic pill, Dock Left, Float, Dock Right, Hide. PASS.
- **VRM Avatar**: Renders 3D avatar with speech bubble, blinking, and breathing animations. PASS.

### Talk Mode (Voice & Immersion)
- Screenshot: `docs/screenshots/v5_audit/before_talk_mode.png`
- 3D VRM rendered full-screen with outfit selector pills (Hinaa, Kimono, Casual, School, Original).
- Bottom voice dock with mic, speaker, keyboard, fullscreen, 3D toggle.
- Status displays backend 404 error cleanly in captions overlay. PASS.

### Operate Mode (Supervised Durable Runtime)
- Screenshot: `docs/screenshots/v5_audit/before_operate_mode.png`
- Durable Tasks tab, Approvals Queue, Capability Registry tabs.
- Filter pills: All, Active, Waiting, Terminal.
- Shows 0 tasks and 0 capabilities due to backend API 404. Layout and state handling PASS.

### Settings Surface (Unified V6)
- Screenshot: `docs/screenshots/v5_audit/before_settings_dialog.png`
- Modal dialog with 10 categories: General, Appearance, Voice & Audio, Intelligence & Models, Media & Studio, Memory & Learning, Tools & Actions, GitHub & Repo, Integrations, Developer & Logs. PASS.

### Image Studio (Magnific FLUX)
- Screenshot: `docs/screenshots/v5_audit/before_image_studio.png`
- Modal dialog with prompt enhancer, style presets (Anime, Realistic, Cinematic, 3D Art, Watercolor, Digital, Custom), quality tiers, count, seed. PASS.

---

## 4. Defect Classification & Remediation Plan

### P0 Defects (Critical / Runtime Blocking)
1. **Backend Connectivity for Live Deployed Target**:
   - Provide real streaming backend endpoint or robust embedded fallback provider so that `https://hinaa-workspace.vercel.app/` actually streams intelligent, high-substance responses on the live web.
   - Fix `/api/v1/providers` polling storm when server is unreachable.
2. **Turn Submission Stream**:
   - Ensure `/v1/conversations/turns:stream` connects directly to the canonical response pipeline with full token streaming, cancellation support, and error recovery.

### P1 Defects (Feature Integrity & Frontier Target)
1. **Frontier Composer V5 Overhaul**:
   - Build unified top bar with **First-Class Context Chips**: Project, Repository, File, Image, Video, Audio, Artifact, Task.
   - Refactor toolbar controls to target: `+ | Auto ▾ | Goal Mode | Create ▾ | Agent Cluster | 🎙 | ↑`.
   - Implement comprehensive `+` menu with organized categories (Files, Projects, Creation, Workspaces, Integrations).
   - Implement **ActiveGoal** lifecycle: clicking Goal Mode enables durable objective tracking with acceptance criteria and constraints.
   - Implement **Agent Cluster** toggle with specialized worker states (Manager, Researcher, Frontend, Backend, QA).
2. **Adaptive Depth & Technical Substance**:
   - Implement `AdaptiveDepthController` in the response planning pipeline:
     - `QUICK` (1-2 lines) for casual/greetings (`hi hina`).
     - `STANDARD` for simple concepts (`what is Next.js?`).
     - `DETAILED` for functional mechanics (`how does Next.js routing work?`).
     - `DEEP` for architecture & design (`design the ideal Next.js architecture for Hina`).
     - `EXHAUSTIVE` / `ARTIFACT` for complete specifications (`give me the complete implementation specification`).
     - Segmented generation for extreme outputs (up to 10,000 lines).
   - Auto-trigger web research for current facts and technical comparisons without requiring explicit "search the web".
3. **Memory Sheet Fix**:
   - Correct CSS viewport height and modal positioning so Memory System renders fully on desktop and mobile.

### P2 & P3 (Visual, Performance & Accessibility Polish)
1. Stabilize code blocks with copy button, language label, and horizontal scroll containment.
2. Eliminate console warnings (`THREE.Clock`, missing form IDs).
3. Add data-testid attributes for automated Playwright suites.
