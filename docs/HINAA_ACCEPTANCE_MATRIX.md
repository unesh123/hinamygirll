# HINAA Acceptance Matrix

> **Evidence rule.** “Code verified” means the implementation passed the repository release gate. “Windows evidence required” means the behavior depends on the user’s browser, microphone, speaker, VSeeFace process, local GPU service, or private API keys and cannot be honestly asserted from the sandbox.

| Capability | Code/test evidence | Current acceptance state | Required final evidence |
|---|---|---|---|
| Typed chat structured turns | Claude-plan normalization, fenced-plan suppression, response-quality tests, full API/web suite | **Code verified** | One post-restart Windows conversation showing natural text and concise speech |
| Qwen provider | Qwen settings, status, typed and realtime forwarding tests | **Code verified; sandbox key absent** | `diagnose-qwen.bat` reports available after Windows API restart, then one real answer |
| You.com research | Search, cited answer, deep/exhaustive effort selection, attributed source renderer tests | **Code verified; sandbox key absent** | One approved deep-research request with visible sources and saved project artifact |
| Local ComfyUI generation | Durable jobs, queue-aware independent variations, polling and result-slot tests | **Code verified; sandbox ComfyUI absent** | One image, refresh persistence, then four variation slots completing on Windows |
| Local documents | PDF/DOCX/PPTX/text extraction and project artifact ownership tests | **Code verified** | Upload a representative private document and inspect its local project artifact |
| Humanizer | Private local endpoint, protected code/link preservation, UI route/privacy display tests | **Code verified** | Open `@humanize`, paste a draft, and verify “Finished locally” plus expected protected content |
| Browser voice / ElevenLabs | Playback queue, replay/mute, typed/live controller tests | **Code verified; sandbox key absent** | One typed and one live Windows turn: audio plays once, mouth moves, audio ends, mouth closes |
| Fullscreen live voice | Overlay, transcript, mobile layout, realtime status tests | **Code verified** | Browser microphone permission, transcript, brain response, audible reply, and composer recovery |
| VSeeFace bridge truthfulness | Fresh external packet gating, stale/synthetic rejection, VMC bridge tests | **Code verified; real packets previously seen** | Imported VRM portrait view; neutral calibration; blink, gaze, head movement, and mouth response in Windows |
| Imported VRM posture | Stronger generic relaxed-pose preset, reset-on-import presentation, app/avatar tests | **Code verified; visual result pending** | Reset model view → Relax arms → Portrait; confirm both arms remain below shoulder level in fullscreen |
| Task workspace and approvals | Local project/task/artifact persistence and approval-flow regressions | **Code verified** | A complex Windows project: task tree, sources, saved files, one approved consequential action, final artifact |
| Mobile UI | Mobile layout check and responsive component tests | **Code verified** | Browser device/phone check of command menu, humanizer, fullscreen transcript, and voice dock |

## Release-gate record

The current release gate passed the complete API suite, full frontend Vitest suite, mobile layout check, TypeScript compilation, production build, lint, and whitespace validation. Frontend lint reported **0 errors** and **36 non-blocking warnings**. The warnings are cleanup debt; they are not release-blocking behavior failures.

## Windows acceptance order

1. Pull the published branch, restart the backend and frontend, then hard-refresh the browser.
2. Run `diagnose-qwen.bat` if Qwen is unavailable. Do not reveal the key in a screenshot or chat.
3. In Avatar Lab, apply **Reset model view → Relax arms → Portrait** to the imported model before testing VSeeFace.
4. Test one typed turn and one fullscreen live turn from microphone start to audible completion/mouth reset.
5. Test one ComfyUI image and then four variations. Keep the local concurrency default at one active GPU job until results are stable.
6. Run an approved deep-research task, save a source to a local project, analyze one private document, and test `@humanize`.

A failed row should be reported with its exact safe visible diagnostic, not a provider key, raw database content, or private document text.
