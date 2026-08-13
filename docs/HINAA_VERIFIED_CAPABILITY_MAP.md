# HINAA Verified Capability Map

> **Purpose.** This map turns the request for a “100+ feature” assistant into an implementable local-first product backlog. A listed capability is either already present, concretely buildable on the current HINAA architecture, or explicitly marked as requiring a local runtime/service. It is not a claim that every external integration is already active.

## Product direction

HINAA should behave as a **warm companion and capable local workspace agent**. Simple messages should receive concise natural answers. Work that needs sources, files, planning, images, or approved external actions should expand into a visible task tree, durable project artifacts, attributable evidence, and a short spoken summary.

Current local-first products demonstrate the value of project-scoped files, task boards, memory, and tool routing, while also showing why those systems must be deliberately staged rather than added as decorative buttons. [1] A practical companion must remain private by default, explicit before consequential external actions, and clear when a local dependency—not the model—is unavailable.

| Product lane | Present HINAA foundation | Next verified increment | Local dependency or boundary |
|---|---|---|---|
| Companion chat | Structured display/spoken turn contract, voice routing, project memory | Conversation-aware suggestions, response mode memory, draft/revision loop | Model provider availability remains visible in settings |
| Research | You.com search, cited answer, page extraction, deep-research tool | Deep/exhaustive effort selection, source-domain filters, background research task timeline | Each research call stays approval-gated because higher effort can take longer and use provider credits [2] |
| Project workspace | Local projects, task tree, artifacts, document extraction | Linked references, research-to-project artifact bundle, document-aware chat context | Files remain in the local workspace unless an approved provider call is needed |
| Document creation | Local extraction for PDF/DOCX/PPTX/text | Markdown report, DOCX/PPTX generation, citation bibliography, review/export queue | Office rendering/export needs local libraries and release-gate evidence |
| Image studio | Local ComfyUI job persistence and independent variation slots | Prompt recipe library, seed/revision history, img2img and controlled batch profiles | ComfyUI must be running locally; an 8 GB GPU should start with one active rendering job |
| Agent execution | Task trees, tool proposals, approval controls, browser ownership safeguards | Reversible task checkpoints, capability-specific reviewers, project artifacts from each completed step | Any external write, login, send, purchase, or browser action stays explicitly approved |
| Voice | Browser/ElevenLabs routes, fullscreen controls, transcript cards | Endpoint diagnostics, barge-in tuning, voice-choice per language, final local acceptance harness | Microphone, speaker, ElevenLabs credentials, and browser permission require Windows evidence |
| Avatar | Browser VRM renderer, relaxed pose protection, calibrated face/head bridge | Per-import rig calibration profile, face expression calibration, portrait presets | No VRM binary edits; real VSeeFace packet/camera proof is required for tracking claims |
| Provider intelligence | CX-first routing, Claude/Qwen optional providers, safe diagnostics | Health-aware fallback, model quality/latency preference, locally visible model tests | Provider keys remain backend-only and never enter project artifacts |
| Skills and extensions | Existing deterministic tool registry and local projects | Scoped skills manifest, reviewable install screen, capability grants per project | Any third-party extension must be inspected and granted only the minimum access |

## The capability catalog

The following catalog is grouped to make the scope tractable. Each line is a separately testable product capability, not an unverified checkbox. This structure provides more than one hundred candidates across twelve delivery domains.

| Domain | Capability families | Readiness direction |
|---|---|---|
| 1. Conversation and persona | Turn memory, response-length control, draft continuations, rewrite tone, decision framing, follow-up only when needed, persistent preferences, conversation search, branch chat, pinned turns | Build incrementally in the existing canonical turn system |
| 2. Research and evidence | Search, cited answer, deep research, exhaustive research, source filtering, content extraction, recency control, domain trust labels, research task status, evidence bundle export | Expand the existing You.com-backed tool path [2] |
| 3. Project workspaces | Local projects, task tree, priorities, milestones, artifacts, project notes, linked research, reusable templates, archive/restore, ownership audit | Extend the current SQLite/workspace layer |
| 4. Documents and artifacts | PDF extraction, DOCX extraction, PPTX extraction, markdown reports, DOCX generation, PPTX generation, citations, summaries, comparison tables, export history | Extraction is available; generation needs a separate validated release |
| 5. Image creation | Prompt editor, independent variations, seed history, image library, image-to-image, control references, upscaling, background removal, project save, export metadata | Local ComfyUI integration only; model/workflow availability must be reported honestly |
| 6. Coding and technical work | File analysis, code explanation, patch proposal, diff review, test plan, test execution, error diagnosis, repository task tree, changelog drafting, release checklist | Safe local file actions first; shell or Git writes require explicit approval |
| 7. Approved automation | Browser research, link collection, local file organization, task reminders, email drafts, calendar drafts, workflow templates, scheduled summaries, webhook intake, notifications | External effects require clearly scoped approval and durable status |
| 8. Knowledge and memory | Personal preferences, project memory, local document index, source notes, citations, decisions, retrieval controls, memory review, forget controls, backup/export | Local-first storage plus user-visible memory management |
| 9. Voice and accessibility | Typed-to-speech, voice interruption, replay, mute, live transcript, language-aware voice selection, captions, keyboard control, reduced motion, screen-reader labels | Physical audio and microphone behavior need device-level acceptance evidence |
| 10. Avatar and presence | Portrait mode, upper-body mode, fullscreen, relaxed pose, per-model facing, camera reset, VMC diagnostics, neutral calibration, expression map, lip-sync | The VMC protocol carries bones and blendshapes, but sender/receiver compatibility and VRM version differences must be handled explicitly [3] |
| 11. Integration and providers | CX, Claude, Qwen, local compatible models, You.com, ElevenLabs, ComfyUI, browser tools, calendar/email connectors, custom skills, MCP-style adapters | Each integration receives a safe status panel and key-free diagnostic |
| 12. Security and operations | Approval gates, secret isolation, project ownership, audit log, task cancel, retry policy, provider fallback, backups, local diagnostics, release gates | Every new capability must ship with its own failure and ownership behavior |

## Delivery sequence

The next delivery steps should be determined by evidence and dependency, not by a raw feature count.

| Stage | Highest-value outcome | Why it comes before the next stage |
|---|---|---|
| **A. Windows acceptance** | Fix imported-model pose/calibration and verify one complete voice turn, one real Qwen or Claude response, one real ComfyUI result | A polished UI cannot compensate for unverified local runtime dependencies |
| **B. Research workspace** | Deep/exhaustive approval cards, background research task status, source save bundle, research report artifact | Builds directly on the user’s existing You.com key and makes research visibly trustworthy |
| **C. Document creator** | Turn local extracted documents and research into a cited Markdown report, then add DOCX/PPTX export | Keeps content creation local and reviewable before introducing additional integrations |
| **D. Agent reliability** | Checkpoints, retries, task ownership, project artifacts, and explicit approval at each consequential boundary | Makes complex task completion dependable rather than merely autonomous-looking |
| **E. Extension platform** | Per-project skills, capability grants, integration tests, and local model routing | Avoids unreviewed plugins or broad permissions from weakening a private companion |

## Automation choices

HINAA can support automation in two safe ways. The correct choice depends on whether the user needs immediate background monitoring or occasional judgment-heavy work.

| Approach | Trade-offs | Cost | Setup complexity |
|---|---|---|---|
| **In-app approved task runs** | Best for research, document work, browser collection, and irregular high-judgment tasks. HINAA remains open while the task runs and the user approves consequential steps. | Uses the configured model/API provider only when the task runs. | Low |
| **Local background worker with visible rules** | Best for persistent reminders, folder watching, webhook intake, or recurring deterministic checks. Needs a Windows-local service, a control screen, and recoverable logs. | Depends on the selected local or cloud service; can be near-zero for local deterministic checks. | Higher |

HINAA should not pretend that a background worker is active until it is installed, configured, and shown as healthy in the local runtime.

## Avatar and VSeeFace acceptance contract

The screenshot supplied on 2026-08-13 proves that fresh VMC packets were received. It does **not** prove that the imported VRM’s axes, full-body rig, facial blendshape mapping, camera capture, or browser mouth timing are correct. VMC uses OSC over UDP/IP and intentionally allows implementations to consume only the messages they need; it also documents VRM 0.x/1.0 expression and control-rig differences. [3]

> HINAA’s browser companion will keep arms in a relaxed local pose and use only calibrated fresh external face/head data. This is intentional: blindly applying every incoming body bone is a common cause of twisted wrists, T-poses, or an avatar leaving frame.

For an imported model, success requires all of the following local checks: portrait camera is centered on face and shoulders; “Relax arms” visibly lowers both arms; VMC reports external packets live; neutral calibration succeeds; a blink and mouth movement reach the correct blendshapes; and ending audio closes the mouth. If a particular model still fails after the stronger generic companion preset, it needs a persisted **per-model calibration profile**, not a changed VRM binary.

## References

[1]: https://github.com/OpenLoaf/OpenLoaf "OpenLoaf local-first project workspace architecture"
[2]: https://you.com/docs/guides/research "You.com Research API overview"
[3]: https://protocol.vmc.info/english.html "Virtual Motion Capture Protocol specification"
[4]: https://github.com/agentscope-ai/QwenPaw "QwenPaw local personal-agent capability reference"
