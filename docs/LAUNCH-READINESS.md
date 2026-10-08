# Hina launch readiness — 6 October 2026

Live workspace: https://hinaa-workspace.vercel.app

## Delivered and checked

- Authenticated owner workspace connects; anonymous protected API requests return 401.
- Desktop router opens in a body portal with bounded positioning, keyboard navigation, and outside-click handling. Header companion no longer covers controls.
- Mobile chat/avatar switcher restored, excessive CSS feature hiding removed, compact HINA header added. Router measured inside a 393px viewport.
- Failed model loads and interrupted GPU contexts now show a clear recovery message and a retry action. Stale load callbacks cannot overwrite a newer attempt; late model resources are disposed. A development global that retained the loaded rig was removed.
- Mobile companion uses the main optimized renderer and saved model calibration. Avatar pixel density is bounded, per-frame temporary allocations reduced, expensive shadows baked once, and offscreen animation paused with demand rendering.
- Thinking timeline follows actual listening/thinking/working/speaking state.
- Windows terminal subprocess execution runs off the async event loop, validates workspace paths, times out and reaps its own child processes. Runtime selection reaches the backend. UI HTTP errors and timeout recovery are explicit.
- Real PowerShell and installed kali-linux commands succeeded. Authenticated local UI returned HINA_UI_TERMINAL_OK with exit code 0.
- Unlinked optimistic image/PDF progress cards no longer get inserted as running jobs. Failed tool results override image-card progress and polling has bounded timeouts. Empty saved image results now show failure instead of completion. Downloads validate HTTP status and image content, have a 30-second deadline, show retryable errors and never commit a failed download as saved.
- Image APIs use the selected host's authentication header. Video model IDs no longer enter still-image generation. Duplicate upscale implementations consolidated; reference editing uses the Kontext task API. Unsupported reference pipelines fail explicitly. Placeholder graphics and copied input images no longer count as completed renders.
- Empty browser voice catalogs no longer break speech fallback at startup.
- Concurrent sign-in identity insertion now handles a losing unique-key insert and reuses the existing account.
- AI instructions distinguish configured versus verified providers and queued versus completed deliverables.

- Document extraction no longer references a nonexistent settings field. Uploads are bounded to 10 MiB, client filenames cannot control temporary paths, extraction runs off the event loop, temporary files are removed and invalid binaries do not become fake text results. The production PDF parser dependency is pinned.
- Cloud API packaging excludes secrets and runtime data, runs as a non-root user, persists state in named volumes, binds the API to host loopback and rejects insecure production configuration. See [cloud deployment](CLOUD-DEPLOYMENT.md); host/container execution remains pending.

- Progressive speech begins from visible streamed phrases while generation continues, with ordered playback, bounded prefetch, cancellation and complete replay. Hidden reasoning/code do not enter speech; fast live synthesis has an 8-second provider budget. Existing streaming providers support overlap; nonstreaming responses cannot speak before text exists.
- Avatar conversational motion is bounded around authored poses and driven by speech energy; mouth timing resets per phrase. The supplied local animation video informed expressive style, not motion capture. Measured frame rate and audible synchronization remain unverified.
- Outlook now has a real delegated Microsoft Graph connector, encrypted Windows token cache, refresh rotation, inbox read and saved drafts. Disconnected email cannot report simulated delivery. Actual school-account sign-in is still required.
- SaaS cards match backend response fields, recover from HTTP/action errors and show configured versus disconnected status. Fake calendar events removed. Terminal status distinguishes local Kali from a live PC session requiring owner pairing.
- Desktop daemon requires a private pairing token, rejects browser-origin requests and bounds action payloads. Editor launch surfaces process errors and no longer claims verified windows. Owner-bound PC grants now authorize scoped host tools for 15 minutes, including voice ticket propagation; actual PC actuation and independent cloud-to-PC relay remain unverified. See [connection requirements](AUTOMATION-CONNECTIONS.md).

- Added official GitHub MCP read-only transport with initialization, discovery, bounded JSON/SSE responses, read-only tool selection, session cleanup and an agent-facing tool. No GitHub credential is available, so real account connectivity remains unverified.
- Diagnostics records actual first-playback onset, synthesis latency and active avatar render-loop FPS/p95 frame interval; no missing sample is presented as a successful measurement.
- Added a persistent Caddy HTTPS edge for independent Linux hosting. Compose parsing and production environment checks passed; Docker Linux engine and real cloud host runtime remain unverified.

## Validation

Latest production deployment: https://hinaa-workspace-6g4ll75gy-uneshs-projects.vercel.app (aliased to https://hinaa-workspace.vercel.app). Production TypeScript/Vite build and Vercel deployment completed successfully. At 17:43:18 UTC the supervised runner reported API, frontend and tunnel healthy with no deployment error. Latest full frontend suite: 81 files, 536 passed, 2 todo. Latest PC/MCP/Clerk/voice transport/Outlook/policy group: 64 passed; final policy/MCP regression group: 17 passed; cloud configuration/document regression group: 14 passed. The earlier brain-coordinator/intent/progressive-voice group passed 100 checks before this deployment. Real PowerShell and Kali checks returned HINA_POWERSHELL_OK and HINA_KALI_OK with exit code 0. DPAPI cache encryption and daemon authorization were tested with synthetic credentials; no real email was sent.

Final deployment browser behavior remains UNVERIFIED. Browser verification was deferred at the user's request after repeated saved-permission rejections; earlier geometry checks do not verify this latest deployment. School OAuth consent/inbox/drafts, actual editor windows and full PC/browser automation, device voice latency and GPU performance remain outstanding.

Latest image-download and WorkMode regression group: 31 passed, including missing deliverables, HTTP download failure and non-image responses. Production TypeScript/Vite build passed. Latest full frontend suite: 517 passed, 2 todo; latest document-upload/document-context/Clerk/cloud-startup group: 28 passed; final upload/cloud-origin regression group: 14 passed; subsequent affected mobile/router/thinking suite: 37 passed, including thinking-state transition coverage. Latest image/reference/provider/adapter group: 52 passed. Earlier image/terminal/provider group: 63 passed; follow-up regression group with two new reference/upscale contracts: 36 passed. PDF/document/vision/config/Clerk group: 59 passed; memory/privacy/Clerk group: 25 passed. Final affected UI group: 33 passed. Groups overlap; do not add these totals. Earlier full backend run had 1636 passes and one configuration-test isolation failure, subsequently corrected and covered in the passing config group. The entire backend suite was not rerun after final edits. Browser GPU performance is hardware dependent; no universal frame-rate guarantee.

## Credentials and services still required

| Capability | Current evidence | Required action |
|---|---|---|
| Direct OpenAI models/images | OPENAI_API_KEY absent | Add an authorized OpenAI API key with model access and billing; the direct GPT Image path is wired with supported dimensions/output format and contract tests; validate it using your authorized account. For a custom image proxy, configure OPENAI_IMAGE_API_KEY, OPENAI_IMAGE_BASE_URL and OPENAI_IMAGE_MODEL explicitly. This alone does not create a desktop controller. |
| GitHub authenticated operations | GITHUB_TOKEN absent | Add a least-privilege GitHub token or GitHub App credentials for the intended repository; configure HINAA_GITHUB_DEFAULT_REPO. Git CLI is distinct from a Git MCP server. |
| Cloud images | Magnific, Freepik, Stability keys present | Validate vendor account credits, permitted endpoints, and an actual render. Current Freepik text-only configuration cannot preserve a reference; use an authorized reference-capable endpoint. A real Stability Core request returned HTTP 402: insufficient account credits. Fund that existing account or validate another authorized provider. The other configured gateway returned HTTP 422: Account not found. Correct the Freepik/Magnific account/key or connect another authorized image API. Reference rendering remains unverified. |
| Local image generation | ComfyUI 127.0.0.1:8188 unreachable | Start ComfyUI with the required models/workflows, or use a validated cloud provider. A generic endpoint is not sufficient for every reference/edit operation. |
| Voice | ElevenLabs key present | Verify voice/model permissions, credits, and live microphone/audio behavior on the target device. Browser speech remains a fallback. |
| LLM routing | 14 configured providers | Catalog presence is not a successful inference. Verify selected providers/models with real calls; quota and vendor availability may differ. |
| Public authentication | Clerk development instance currently used | Configure a Clerk production instance and production domain before treating this as a finished enterprise launch. Keep the owner allowlist. |

OpenAI image contract: https://developers.openai.com/api/docs/guides/image-generation

Image contracts: https://docs.magnific.com/api-reference/text-to-image/flux-kontext-pro/overview and https://docs.magnific.com/api-reference/text-to-image/flux-dev/post-flux-dev

## Always-on hosting

The frontend is deployed on Vercel. The backend currently runs on this PC through a supervised runner and a temporary Cloudflare tunnel. The PC must remain awake and online. This is live but not independent 24/7 cloud hosting.

For a durable VPS/cloud deployment, provide the intended account/project, domain and resource budget. Deploy the API as a supervised container/service with persistent database and private artifact storage, TLS, production Clerk settings, secrets management, backups, health checks and logging. Replace temporary tunnel rewrites with a stable backend origin. Do not put private memories or backend secrets into frontend assets. A GPU is needed only if choosing local/cloud self-hosted image or model inference.

## PC and browser control

Local terminal and installed Kali are functional. The public site intentionally cannot execute unrestricted commands on the physical PC. Browser automation, Git MCP, native app automation, and remote PC control require distinct running adapters/controllers; a model API key or VPS does not supply them.

For remote control, use a paired authenticated desktop agent with explicit task permissions, execution/audit logs, cancellation, and approval for consequential actions. Run it locally for physical-PC access; keep its command endpoint private. Use a VM or isolated desktop if Hina must operate a mouse without interfering with your own cursor. Native app reliability must be verified app by app; arbitrary universal task completion has not been established.

OpenAI's controller-loop requirements: https://developers.openai.com/api/docs/guides/tools-computer-use

## Remaining launch blockers

Stable always-on backend hosting; production Clerk configuration; Stability account credits and successful cloud image/reference validation; GitHub/MCP credentials and a running server; paired remote desktop control; target-device voice and GPU performance acceptance. These are not marked complete by a green build or configured key.
