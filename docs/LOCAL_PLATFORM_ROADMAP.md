# Hinaa Local-First Platform Roadmap

## Product Direction

Hinaa will evolve from a conversation screen into a **private, local-first AI companion workspace**. The product will keep user projects, files, generated media, conversations, research material, plans, and agent outputs on the local machine by default. It will remain extensible: individual AI brains, image backends, voice engines, and tools will be replaceable adapters rather than hard-wired product dependencies.

The target experience is a calm companion that can converse naturally, ask useful follow-up questions, propose structured options, complete complex multi-step work, retain only user-approved memory, and show exactly what it is doing. Hinaa should be proactive without acting secretly: she plans, explains, asks for confirmation before consequential actions, and preserves artifacts inside the relevant local project.

## Architectural Principles

| Principle | Product rule |
|---|---|
| Local by default | Projects, source files, uploads, generated images, research notes, plans, and memory remain in a configurable local data directory. |
| Explicit agency | The model can propose tasks and tool calls, but the user approves consequential actions before execution. |
| Durable artifacts | Every useful output has a project, source, status, timestamp, and local path or content record. |
| Replaceable providers | Text models, local image backends, voice engines, web research, and avatar rendering are accessed through narrow provider interfaces. |
| Progressive disclosure | Casual conversations stay warm and concise; complex work expands into plans, progress, citations, and artifact cards. |
| Safe concurrency | Independent read-only work can run concurrently with limits; file writes, browser actions, communication, and destructive steps remain gated. |
| Honest capability status | Each feature exposes whether it is ready, queued, unavailable, or needs a local service such as ComfyUI. |

## Combined Capability Roadmap

### 1. Local Agent Workspace

The workspace foundation includes local projects, project folders, editable metadata, local file imports, artifact records, chat-to-project conversion, and a structured task tree. Each task will show a title, outcome, status, dependencies, source context, and approval state. Independent, read-only research or analysis tasks can run in parallel behind a bounded queue, while actions that alter files or interact with external services remain sequential and user-approved.

A project detail view will organize conversation threads, source links, uploaded files, generated assets, exports, plans, and task history. Local search will index project titles, filenames, and artifact text. The initial implementation will use SQLite for metadata and a clear on-disk project directory for original files and generated outputs.

### 2. Multimodal Creator

Hinaa already has a local ComfyUI bridge. The creator layer will add an image studio with aspect ratio, quality, seed, negative-prompt, variation, and project-saving controls. A local image library will group outputs by project and generation set, preserve prompt metadata, and expose download, reuse, variation, and attachment actions.

Image editing will be added only through explicit local workflows such as image-to-image, inpainting, outpainting, and upscaling when the corresponding local ComfyUI workflow is installed and healthy. The interface will never pretend editing is available when the configured local workflow does not support it.

### 3. Research and Structured Work

The research layer will collect URLs, page titles, extracts, timestamps, notes, and citations into a project research board. Hinaa will return structured response cards when a task benefits from them: executive summary, plan, options, sources, assumptions, risks, artifacts, and recommended next action. In ordinary conversation she will remain concise and emotionally attentive.

The planner will produce a task tree rather than opaque chain-of-thought. It will expose goals, milestones, dependencies, expected artifacts, and approval gates. Users can select an option, edit the plan, rerun a failed task, pause execution, or convert a result into a project artifact.

### 4. Companion Intelligence and Expression

Hinaa’s companion layer will support a warm but grounded persona, conversation-aware follow-up questions, user-selectable communication style, and explicit memory permissions. The response renderer will support choices, chips, checklists, source cards, generated-image cards, file cards, and progress panels without making every message overly long.

Voice and avatar work will be separated from the logic layer. The voice pipeline should supply speaking state, timing, and visemes; the avatar adapter should map them to available VRM blendshapes, eye movement, gaze, posture, and emotion states. A procedural companion remains the reliable fallback. A VRM should be enabled only when its license, assets, expression map, and performance budget are validated.

## Delivery Stages

| Stage | First completed capability set | Proof of completion |
|---|---|---|
| Foundation | Projects, local artifact database, file import, task-tree UI, project workspace shell | Create a project, import a file, create a task tree, and reopen the project locally. |
| Creator | Image studio, image job progress, local gallery, prompt metadata, project attachment | Generate using a healthy local image service and save the result to a project. |
| Research and Agent | Source board, structured answer cards, selectable next steps, visible plan and approvals | Collect sources, cite them, save a research artifact, and approve a gated action. |
| Companion Polish | Conversation modes, choices, memory permission UI, voice state, visual emotion mapping | Hinaa holds a smooth contextual conversation and exposes an accurate capability state. |
| Reliability | Tests, cancellation, queues, retries, performance budget, backups, exports | All local workflows recover cleanly and leave inspectable artifacts. |

## Safety and Privacy Boundaries

Hinaa may help with creative and mature fictional work when lawful and consensual, but will not create illegal, exploitative, non-consensual, or harmful content. The image studio will keep provider capability checks and prompt moderation boundaries visible rather than claiming unrestricted generation.

Any step that sends information outside the local machine, controls a browser, communicates with another person, changes or deletes files, or performs a purchase or account action must require a clear confirmation screen. Local read-only analysis can proceed automatically only when the user has started the task and can observe progress.

## First Implementation Increment

The first code increment establishes the durable local workspace that every later feature needs: project and artifact records, a project-file directory convention, project API routes, a client project sidebar and workspace panel, and a basic editable task tree. Image generation, research, and creator outputs will attach to these records in the next increments instead of living as disconnected job data.
