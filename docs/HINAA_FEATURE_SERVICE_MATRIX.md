# HINAA Capability and Service Matrix

> **Design rule.** HINAA is a local-first companion. “Available” means implemented and testable; “requires service” means the user must configure the relevant local program or API; “explicit approval” means HINAA may prepare an action but must obtain an affirmative user confirmation immediately before it acts externally or changes the device.

## Current and near-term capability map

| User request family | Existing HINAA foundation | Next reliable extension | Service or local dependency | Approval requirement |
|---|---|---|---|---|
| Hinglish voice companion | ElevenLabs/STT/TTS routes, browser fallback, live fullscreen state, Hindi × English policy | Noise gating, barge-in, end-of-turn confidence controls, provider-specific realtime option | ElevenLabs key or local STT/TTS; browser microphone and speaker | Microphone permission; no separate approval for a local conversation |
| 3D companion / VSeeFace | VRM avatar, VMC receiver, fresh-packet truthfulness, pose/camera controls | Per-model calibration profiles, blendshape mapping diagnostics, saved neutral calibration | Windows VSeeFace, camera, supported VRM, local VMC packets | User explicitly starts tracking and calibrates neutral |
| Secure local files | Local workspace, ownership-scoped files/artifacts, document extraction | Encryption-at-rest vault, password/OS-backed secret protection, index/search | Windows file APIs or local companion; optional OS credential vault | Required before encrypt/delete/hide/unhide operations |
| Deep research | You.com-backed cited research, visible effort level, sources/task cards | Research report template, source scoring, project artifact/save and export | You.com key for live web research | Required before live web research is executed |
| Slides / reports / documents | Local project artifacts, PDF/DOCX/PPTX extraction, Markdown exports | DOCX/PPTX generation through a verified document pipeline, templates, local preview | Local document generators; optional model brain for drafting | Creating files is local; export/send remains explicit |
| Web reader / scraper | Browser-read/research approvals and source renderer | Safe public-page extraction, tables/links, rate limits, robots/terms visibility | You.com or a browser/local companion; no bypass of login/paywall/access controls | Required before each external browse/scrape sequence |
| Image generation | Local ComfyUI jobs, multi-variation slots, durable results | Workflow selector, aspect controls, image-to-image/edit adapters | Running local ComfyUI and compatible models/GPU | Explicit image-generation action |
| Coding / site builder | Code-help route, project/workspace, task tree | Scoped project scaffold, test/build loop, artifact preview, approved local command runner | Selected brain plus local Node/Python tools | Required before file writes, commands, Git operations, or publishing |
| VS Code workspace | Local project surface only | Trusted Windows companion adapter for open-folder, diagnostics, build/test command proposals | Windows companion / VS Code CLI | Required per workspace open and command execution |
| Shopping / travel / food comparison | Research/search surface | Read-only comparison cards with sources and price timestamp | Public search/provider APIs, subject to terms | Required before opening a merchant or adding/purchasing anything |
| Stocks / crypto / FX | Research surface | Read-only delayed/live market dashboard with time/source labels | Licensed market-data API; do not present as financial advice | No approval for local display; user must decide on trades |
| WhatsApp / email | Approval panel and browser/messaging intent surfaces | Draft composition, recipient selection, message review, one-send confirmation | Official provider/API or user-authenticated browser; WhatsApp Business API has separate eligibility | Required for every send/call; never infer recipient or send silently |
| OCR / screen assistance | Document/image ingestion foundation | User-initiated screenshot/OCR of selected screen/window, local redaction, answer as a draft | Trusted Windows companion, local OCR engine | Required for every capture; never continuous hidden screen monitoring |
| Music / YouTube / Spotify | Music context and explicit browser action proposal | Search and controllable local playback after user confirms target | YouTube/Spotify official APIs or controlled local browser session | Required before playback/control that affects external service |
| System/device controls | No safe direct device agent in web app | Typed/voice proposal → OS-level command preview → final approval → audit log | Trusted Windows companion, device-specific permissions | Required for volume, brightness, processes, Wi-Fi, wallpaper, power, or file changes |
| Scheduling/reminders | Task framework | Local reminder jobs with visible status, cancellation, and audit record | Local backend/Windows companion for OS notifications | Required for recurring jobs and power/system actions |
| AV scan / device health | No antivirus or hardware control inside web app | Read-only Windows Defender/SMART/temperature status adapter; explicit scan proposal | Windows Defender/PowerShell, hardware sensor utility | Required before a scan or cleanup; never delete files automatically |
| Files / ZIP / format conversion | Workspace and exports | Project-scoped, preview-first ZIP/PDF/format conversion actions | Local converters and Windows companion | Required before overwriting/deleting/archive extraction into a target |
| Personal memory | Durable local user-scoped memory and approval model | Memory review, correction, expiry, local semantic index, clear-all control | SQLite/local embeddings for semantic search | Required before durable memory is saved or reused for sensitive tasks |
| Voice identity / face understanding | No biometric authentication feature | Optional on-device user-presence/voice-profile research only; no biometric lock claim without secure enrollment/liveness design | Specialized local biometric stack and OS security controls | Explicit enrollment and revocable consent; never enabled by default |

## What can be built with no additional paid API

The following are achievable locally once the user has the relevant installed software: document parsing and Markdown artifacts, local project/task trees, private deterministic humanizer, local ComfyUI image jobs, local Ollama writing/coding route, OCR over user-approved captures, file indexing in chosen folders, ZIP/PDF conversion, reminders, and a Windows companion that proposes (rather than silently executes) local commands.

## Common API or service choices

| Purpose | Primary route | Free/local alternative | Notes |
|---|---|---|---|
| Reasoning and drafting | Existing Qwen, Claude, CX routing | Ollama with a local model | Provider health and user-controlled selection stay visible |
| Web research | You.com | Public-page manual reading with a local browser | No paywall/login bypass; citations remain visible |
| Image generation | Local ComfyUI | Same | GPU speed is hardware-bound; “0.1 second” full image generation is not realistic on a local RTX 4060 for quality images |
| Speech | ElevenLabs | Browser speech or local STT/TTS | Actual latency depends on model, network, hardware, and audio segment size |
| Search / maps / shopping | Source-specific official APIs | Cited public searches | Read-only research first; no automatic purchases |
| Messaging | Official email/WhatsApp-capable channel or user-controlled browser | Draft-only local output | Always confirm recipient, content, and send action |
| Screen / system actions | Trusted Windows companion | None in a browser-only HINAA install | Requires a scoped local permission model and audit log |

## Explicit non-goals and safety constraints

HINAA must not bypass website access controls, log into accounts without the user selecting/confirming an account, scrape private/paywalled pages contrary to authorization, impersonate people, silently monitor a screen/camera/microphone, learn sensitive information without approval, send messages/calls without a final confirmation, or execute destructive/device actions without an action preview and approval. These are product reliability requirements, not optional personality restrictions.

## Recommended build sequence

1. **Agent foundation:** durable task graph, action proposals, voice-readable approval prompts, final confirmation state, audit log, and recovery after a provider failure.
2. **Work creation:** local site/code workspace, document/PPTX/DOCX export jobs, project artifacts, test/build reports, and image attachments.
3. **Research and files:** scoped web research, citations, PDF/document semantic search, and project knowledge retrieval.
4. **Windows companion:** opt-in local adapter for selected folder/file operations, screen capture, process status, browser handoff, VS Code, media, and system proposals.
5. **Advanced presence:** per-VRM calibration, VSeeFace validation, noise-aware turn taking, and optional local Ollama/voice stack.

The detailed capability roadmap is maintained in `docs/HINAA_VERIFIED_CAPABILITY_MAP.md`; this matrix specifically maps the user-provided catalogue to real dependencies and consent boundaries.
