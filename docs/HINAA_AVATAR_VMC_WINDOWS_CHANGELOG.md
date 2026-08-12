# HINAA Windows Avatar, VSeeFace, VMC, and Live-Presence Changelog

## Safety baseline — 2026-08-13

| Item | Recorded value |
|---|---|
| Isolated working branch | `work/hinaa-avatar-vmc-windows-completion` |
| Base commit | `faab3ce1c5b90cf580815dca810868d319e66eed` |
| Base subject | `Harden image workflow and avatar completion` |
| `origin/main` at baseline | `b9beef440b8b21a6869aa2082381ebf5d5ea2c40` |
| Required baseline commits | `6645bcb` and `5044a8c` are reachable from the base. |
| Prior completion commit | `faab3ce` exists but is **not** an ancestor of `origin/main`; it has not been merged into main. |
| Working tree before this pass | Clean. |

No environment file, SQLite database, private workspace data, webcam data, VMC recording, generated media, non-public VRM asset, or ComfyUI model/workflow is eligible for commit in this pass. No merge to `main` is permitted without a separate explicit user instruction.

## Acceptance baseline and evidence discipline

The supplied screenshot target is a face-and-shoulders **Portrait** companion view with relaxed shoulders and arms, rather than a full-body T-pose. The implementation distinguishes **IMPLEMENTED**, **UNIT_TESTED**, **INTEGRATION_TESTED**, **BROWSER_VERIFIED**, **WINDOWS_RUNTIME_VERIFIED**, **BLOCKED_IN_SANDBOX**, **DEGRADED**, and **FAILED**.

> A bound UDP socket, open browser WebSocket, loaded avatar, or synthetic diagnostic packet is not evidence of real VSeeFace camera tracking. The UI may display **VSeeFace Live** only while valid non-synthetic VMC packets are fresh and continuously observed.

The current Manus environment has no connected Windows desktop configuration. Windows-specific filesystem, VSeeFace process, real camera stream, real packet rate, model import, and browser screenshot validation therefore begin as **BLOCKED_IN_SANDBOX**, not absent or failed on the user's Windows machine. Repository-resolvable behavior will be implemented and tested here; the Windows evidence boundary will be recorded precisely.

## Required work records

| Area | Required result | Initial status |
|---|---|---|
| Default presentation | Portrait is the persisted default; close-up, upper-body, and full-body controls are explicit. | Pending audit |
| Neutral pose | Arms relaxed through cached normalized humanoid rest quaternions, with no cumulative drift or raw-node corrections. | Pending audit |
| LIVE state | Listening, receiving, stale, disconnected, error, and synthetic test are visibly distinct. | Pending audit |
| LIVE control panel | Keyboard-accessible VMC diagnostics and controls provide visible feedback on every action. | Pending audit |
| VMC transport | One receiver, parser, broadcast path, browser consumer, and avatar director; repeated clicks are idempotent. | Pending audit |
| Tracking response | Packet freshness, rate, channels, test source, expression ownership, smoothing, and calibration are supported without false claims. | Pending audit |
| Avatar assets | Approved-root inventory and user-selected import use parse-based VRM version/license/rig diagnostics and opaque managed asset IDs. | Pending audit |
| Avatar Lab | Route/panel exposes implemented model, camera, pose, expression, VMC, and performance details. | Pending audit |
| Regression preservation | Chat recovery, voice fallback, durable ownership, image pipeline, and existing VMC bridge remain intact. | Pending audit |

## Change records

| File | Reason | Evidence | Status |
|---|---|---|---|
| `docs/HINAA_AVATAR_VMC_WINDOWS_CHANGELOG.md` | Establish branch, safety, screenshot target, and evidence boundaries before edits. | Git baseline and session configuration inspection. | **IMPLEMENTED** |

## Audit findings — repository source

| Area | Finding | Consequence | Planned repair |
|---|---|---|---|
| T-pose / arms | `AvatarPresence` is the only avatar implementation mounted by `App`. It captures normalized humanoid rest quaternions but applies identity `POSE_Q` offsets every frame, preserving a model whose authored rest pose is a T-pose. The other `VRMAvatar` variants are not mounted by the active app. | Arms can remain horizontal despite the per-frame “relaxed pose” loop. | Use one centralized, model-specific offset registry relative to immutable cached normalized-bone rest quaternions; apply it through one Avatar Director only. |
| Camera | The app initializes Portrait but an effect resets it to Portrait on state changes and `AvatarPresence` only exposes portrait, close-up, and full. Upper body, model-specific persistence, and user calibration are missing. | The user cannot choose the requested full camera set or preserve a tuned view per model. | Add `upperBody`, per-model persisted view calibration, explicit accessible controls, and an Avatar Lab route/panel. |
| LIVE state | `useVSeeFace` marks state `active` on WebSocket `onopen`; `App` then displays `Face tracking active — expressions mirrored live`, and `AvatarPresence` paints a green LIVE badge. | A bound listener/browser connection is falsely presented as live VSeeFace tracking. | Add backend packet freshness, rate, channels, source type, listener lifecycle, synthetic-test metadata, and frontend states based on diagnostics rather than WebSocket open. |
| VMC bridge | Existing `VMCBridge` is already a singleton receiver/parser/broadcast path. It has no timestamps, packet history/rate, detected-channel inventory, listener status, test source, or diagnostics endpoint. | It is repairable; a second bridge is neither needed nor acceptable. | Extend this bridge in place, keep one receiver, and expose one status endpoint plus an explicit synthetic-test action. |
| Browser VMC consumer | The one active hook opens one WebSocket but cannot distinguish initial state payload from a fresh external packet; callback closure can also use stale `status` on close. | Repeated user actions lack truthfully observable state; no stale transition exists. | Refactor the hook around an idempotent connection ref and a diagnostic polling cadence; keep fast packet samples in refs and coalesce React updates. |
| Asset selection | App only accepts two hard-coded public model URLs and no avatar-specific backend asset API/schema exists. | A user-selected local Windows VRM cannot be inventoried, imported, validated, or selected. | Add managed local avatar storage, parse-based VRM inspection, manifest/provenance, opaque IDs, delete confirmation UI, and a safe browser model URL API. |
| Live Windows evidence | Session configuration shows no connected Windows desktop; the sandbox VMC test is explicitly synthetic. | No real Windows asset/process/camera assertion or screenshot can be made. | Implement the controls and diagnostics, then mark real Windows camera/model evidence **BLOCKED_IN_SANDBOX** until a desktop is connected. |

## Completion record — 2026-08-13

| Area | Implemented result | Evidence status | Evidence |
|---|---|---|---|
| One VMC transport | The existing singleton `VMCBridge` remains the only UDP receiver/parser/WebSocket fan-out. No second socket, canvas, or bridge was added. | **INTEGRATION_TESTED** | API starts one receiver on `127.0.0.1:39539`; explicit status exposes one receiver instance ID and listener state. |
| Truthful LIVE semantics | The bridge records timestamp, source, packet count/rate, channel inventory, sender summary, stale age, and a 3-packet/s continuous external-stream threshold. `listening`, `test`, `stale`, `live`, `disconnected`, and frontend `error` are distinct. | **INTEGRATION_TESTED** | Runtime sequence returned `listening` → explicit `test` with `source: synthetic` → `stale` after 2.01 s. Focused bridge test covers continuous external burst → `live` and then stale. |
| LIVE control | The avatar pill opens `VmcControlPanel`, an accessible non-modal local control surface with connect/listen, disconnect, reconnect, test signal, calibrate, reset, status, packet age/rate, channel list, selected model/mode, and setup text. | **UNIT_TESTED** | `VmcControlPanel.test.tsx` verifies a listening bridge does not render `VSeeFace Live` and disables neutral calibration. |
| Browser consumer | `useVSeeFace` keeps one idempotent WebSocket, polls diagnostics at 500 ms, coalesces high-rate samples into refs, and resets stale/disconnected samples safely. | **IMPLEMENTED** | Type check and 24-file frontend test run pass. |
| Conversational camera | Portrait is the default and persists per avatar; close-up, upper body, and full body are explicit. Anatomy uses head/neck/chest/hips to prevent bounds-driven full-body framing. | **IMPLEMENTED** | Type check and production build pass. Real Windows screenshot evidence remains blocked. |
| Neutral pose | `AvatarPresence` caches immutable normalized humanoid rest quaternions and uses a central per-model target profile. `model_6164` and `model_5447` have mirrored upper-arm/lower-arm shoulder offsets; unknown imports keep authored rest. No raw-node correction or accumulated Euler pose is used. | **IMPLEMENTED** | Source audit, type check, production build. Visual Windows asset confirmation remains blocked. |
| Face/head ownership | TTS owns mouth visemes during speech. Fresh live VMC drives non-speech vowels, blink, mapped emotion. VMC head rotation is only applied after external-live neutral calibration, is relative to that baseline, bounded to 22°, and ignores uncalibrated body/limb data. | **IMPLEMENTED** | Code-level safety review, typed build. Real sender/model result blocked. |
| Avatar strategy modes | Avatar Lab visibly distinguishes HINAA Autonomous, Exact VSeeFace Model (only VRM 0.x candidate selectable), and VSeeFace Tracking Proxy. Proxy is labelled as non-exact and requires calibration for head motion. | **IMPLEMENTED** | Production build; parser inventory behavior tested. |
| Local asset handling | API scans only approved application roots and managed HINAA assets. File picker import parse-validates VRM/glTF metadata, copies into opaque-ID managed storage, serves a safe browser URL, and deletes only managed copies after browser confirmation plus `confirm=true`. | **UNIT_TESTED** | `test_vmc_and_avatar_assets.py` validates parse-based 0.x candidate vs 1.0 incompatibility. Parsed repository inventory is recorded in `HINAA_WINDOWS_VRM_ASSET_INVENTORY.md`. |
| Avatar Lab | The existing HINAA drawer hosts Avatar Lab; it adds no second avatar canvas. It provides inventory, import/delete, model metadata, camera controls, strategy mode, VMC diagnostics, calibration, and explicit ownership language. | **IMPLEMENTED** | Type check and production build. |
| Sidebar | Every rail button now has a keyboard-accessible label/title. The current availability/error matrix is documented in `HINAA_SIDEBAR_CAPABILITY_MATRIX.md`. | **IMPLEMENTED** | Source audit and frontend suite. |
| Regression preservation | Chat recovery, fallback voice, workspace, image pipeline, and ownership code were not replaced. | **REGRESSION_TESTED** | Backend `pytest -q` passed; frontend suite passed. |

### Release gates

| Gate | Result |
|---|---|
| Backend test suite | **PASS** — 171 tests, including 2 new VMC/avatar-asset tests. |
| Frontend test suite | **PASS** — 24 files, 107 passing tests, 2 existing todos. |
| Frontend type check | **PASS** — `tsc -b`. |
| Production build | **PASS** — Vite/PWA production build. |
| Local API runtime | **PASS** — `health/live`, VMC status/test/stale endpoints, and asset inventory returned expected contracts. |

### Evidence boundary at handoff

| Requirement | Status | Why |
|---|---|---|
| Real Windows `5798998195377315936 (1).vrm` discovery, metadata inspection, import, and selection | **BLOCKED_IN_SANDBOX** | No connected Windows desktop/filesystem is available in this session. Sandbox results are not substituted for Windows evidence. |
| Real VSeeFace process/window health | **BLOCKED_IN_SANDBOX** | No user Windows desktop process can be inspected. |
| Real camera motion, sustained VSeeFace packet rate, and browser screenshot/video showing blink/mouth/gaze/head response | **BLOCKED_IN_SANDBOX** | No Windows VSeeFace sender or camera stream is connected. The only exercised runtime fixture was explicitly labelled synthetic and was never displayed as LIVE. |
| Final visual portrait/relaxed-hand screenshot of the requested user model | **BLOCKED_IN_SANDBOX** | Requires the actual selected Windows model loaded in that browser/runtime. |

No VRM binary, ComfyUI model/workflow, secret, database, generated media, browser profile, or user-selected original avatar was modified by this pass.


## VSeeFace control-panel hotfix — 2026-08-13

The user reported that clicking the visible **VSeeFace** pill did not open the expected panel. The supplied Antigravity conversation confirmed that the earlier branch had been merged into the local Windows workspace and the page contained the current button/status copy; a hard refresh alone therefore could not be accepted as a repair.

| Trace point | Finding | Result |
|---|---|---|
| Avatar pill handler | The button still calls the current drawer-state path and creates `VmcControlPanel`; the app-level regression reaches the portal dialog. | **PASS** |
| VMC API route | `/api/v1/vmc/status` is correctly proxy-rewritten to the local backend; WebSocket remains the existing direct local endpoint. | **PASS** |
| Portal host | `HinaDrawer` uses `createPortal(document.body)`, but the active `App.css` contained no `.hina-drawer-*` layout/stacking rules. The portal therefore rendered as ordinary unstyled document flow behind/below the fixed shell, which appears as a no-op. | **ROOT CAUSE CONFIRMED** |
| Repair | Added fixed portal overlay/backdrop, a high isolated stacking context, interactive panel, responsive bottom/side geometry, header, close button, and scroll body styles. | **IMPLEMENTED** |
| Regression | Added an app-level click test that presses the real VSeeFace control and asserts the visible `VSeeFace and VMC connection panel` dialog plus its disconnected guidance. | **PASS** |
| Browser automation | After connecting My Browser, the local Windows HINAA UI was visible and exposed the correct VSeeFace button. Browser extension click/view commands returned HTTP 504 before app state could be inspected. | **DEGRADED — browser automation transport**; not treated as an app-panel failure or tracking evidence. |

### Hotfix release gates

| Gate | Result |
|---|---|
| App-level VSeeFace panel regression | **PASS** — real pill click opens the VMC dialog. |
| Full frontend suite | **PASS** — 24 files, 108 passing tests, 2 existing todos. |
| TypeScript | **PASS** — `tsc -b`. |
| Production build | **PASS** — Vite/PWA production build. |

This hotfix changes only the missing portal presentation and the regression proof. It does not alter the one-bridge VMC protocol, live-state threshold, user model binaries, VSeeFace installation, ComfyUI installation, credentials, or `main`.


## Simple Avatar Workflow and Per-Model Presentation — 2026-08-13

This refinement addresses the reported difficult model switching, backward-facing imported avatars, raised-arm imported poses, and Avatar Lab visual mismatch. It retains the single HINAA renderer, private local import route, original VRM files, and truthful VSeeFace state model.

| Area | Implemented behavior | Evidence |
|---|---|---|
| Direct selection | The persistent selector now exposes only **Hinaa**, **Hinaa Classic**, and **+ Add avatar**. Selecting a local file imports it through the existing private API and immediately selects the returned managed model URL; no second manual selection is required. | App upload/select regression passed. |
| Per-model presentation | `avatarPresentation.ts` persists only browser-scene rotation, ground offset, bounded scale, and `relaxed`/`original` pose mode by model URL. It never writes to a VRM binary. | Four focused persistence/bounds/facing regressions passed. |
| Facing correction | Imported models start in the safe HINAA front-facing preset. The Avatar Lab supplies a one-click **Flip facing** repair and remembers it per model, rather than claiming an unseen authoring axis can be inferred perfectly. | Focused regression passed; real model visual evidence remains runtime-bound. |
| Arm correction | Imported humanoid rigs use conservative rest-relative normalized-bone offsets for a relaxed arm profile. **Original pose** restores the author rest pose if a non-standard rig looks better that way. | Type check and full frontend suite passed. |
| Simpler Avatar Lab | The drawer now uses the mint/pearl HINAA visual system, a current-avatar card, direct local upload, drop-down/chip selection, simple facing/arms/reset controls, camera buttons, and collapsed advanced diagnostics. | Production build passed. |
| VSeeFace limits | Exact VSeeFace remains enabled only for a parsed VRM 0.x compatibility candidate. Tracking Proxy remains visibly proxy-labelled and never drives uncalibrated limbs. | Existing bridge and VMC regressions remain intact. |

### Release gates

| Gate | Result |
|---|---|
| Frontend regression suite | **PASS** — 25 files, 113 passing tests, 2 existing todos. |
| Type check | **PASS** — `tsc -b`. |
| Production build | **PASS** — Vite/PWA build. |

A direct My Browser inspection could load the user’s local HINAA page and display the selector, but browser action commands again failed with extension HTTP 504. That is recorded as browser-automation degradation only; it is not evidence about the user’s model pose, VSeeFace sender, or live tracking.
