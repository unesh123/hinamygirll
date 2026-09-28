# HINA ASTRA — Master Coding Agent Command

Copy everything below into the coding agent that has access to the **real Hina repository**.

---

You are the principal engineer responsible for integrating **HINA ASTRA** into the existing Hina codebase. This is a production integration, not a demo and not a visual mock.

## Mission

Transform Hina from partially separated chat/action/agent systems into a unified multimodal cognitive runtime while preserving all currently working Hina features.

The target architecture is:

```text
INPUT
→ PERCEPTION
→ CONTEXT COMPILER
→ ENTITY RESOLUTION
→ MEMORY RETRIEVAL
→ EXECUTIVE ROUTER
→ CAPABILITY RETRIEVAL
→ PLAN
→ PERMISSION
→ EXECUTION
→ OBSERVATION
→ VERIFICATION
→ BOUNDED REPAIR
→ ARTIFACT GRAPH
→ SEMANTIC EVENT STREAM
→ HINA OBJECT UI / WORKSPACE / CHAT
→ MEMORY + ENTITY UPDATE
```

The language model is one subsystem. Do not turn the entire product into a single giant model prompt.

## Inputs available to you

A reference integration pack is present with:

- `apps/api/astra/`
- `apps/web/src/features/astra/`
- `docs/`
- `contracts/`
- `scripts/`

The reference pack is intentionally isolated so that you can map it onto Hina's real systems instead of blindly overwriting production code.

## Non-negotiable rule 1 — audit before changing code

Before editing production files, inspect the repository and produce an internal integration map covering:

1. API framework and entrypoint.
2. Existing `/v1/chat` or equivalent endpoint.
3. Current streaming protocol.
4. `agent/compiler.py` or current context compiler equivalent.
5. `agent/kernel.py` or current agent loop equivalent.
6. Current model/provider clients and routing.
7. `persistence/orm.py` or current ORM models.
8. Current memory models and retrieval.
9. Current entity/search intelligence and pronoun logic.
10. Existing image search/generation path.
11. Existing document/PDF generation path.
12. Existing web/search/file/code tools.
13. Existing WorkMode / Composer implementation.
14. Existing HinaSurface / HinaActionStack / action cards.
15. Existing artifact/file UI.
16. Existing animation system and Framer Motion usage.
17. Existing authentication and authorization.
18. Existing deployment boundaries: Vercel/server/worker/local sidecar.
19. Current test, lint, typecheck, and build commands.
20. Current production branch and clean working tree state.

Do not assume the paths in this pack are exact. Find the real equivalents.

## Non-negotiable rule 2 — preserve current behavior

Do not regress:

- normal chat
- markdown rendering
- entity-grounded image search
- image generation
- documents/PDFs
- voice/audio
- project/workspace behavior
- file uploads
- authentication
- existing provider routing
- current production actions
- accessibility protections
- URL sanitization
- existing tests

If a current system already solves part of Astra, adapt it rather than duplicating it.

## Non-negotiable rule 3 — one runtime

The current product must not keep one unrelated path for normal chat and another unrelated path for autonomous work.

Create or adapt one runtime entrypoint conceptually equivalent to:

```python
AstraRuntime.run(request)
```

All request types enter it.

Possible routes:

- CHAT
- DIRECT_ACTION
- AGENT_RUN
- WORKSPACE
- CLARIFICATION

Normal chat should remain lightweight. It does not need to invoke planning/tools when unnecessary.

## Non-negotiable rule 4 — one semantic event protocol

Unify UI telemetry around typed events.

Minimum event set:

```text
request.received
context.compiling
context.ready
route.selected
plan.created
step.started
step.completed
tool.started
tool.progress
tool.completed
tool.failed
verification.completed
artifact.created
object.updated
response.delta
run.completed
run.failed
```

Backend is authoritative.

Frontend must not invent execution stages.

Do not show fake progress percentages.

If progress is unknown, show honest states such as:

```text
Generating image…
Working · 12s
Running tests…
Waiting for provider…
```

Never expose private chain-of-thought. Only expose operational telemetry.

## Non-negotiable rule 5 — global entity brain

Move entity/pronoun resolution out of image-search-only code into a global service.

Required flow:

```text
User: Who is Mikasa Ackerman?
→ active entity = Mikasa Ackerman / Attack on Titan

User: tell me more about her
→ her = Mikasa Ackerman

User: show images
→ action = image.search
→ canonical query = Mikasa Ackerman Attack on Titan
```

Never allow this to become:

```text
image query = "tell me more about her"
```

Entity state must support:

- canonical name
- aliases
- type
- domain/franchise
- attributes
- confidence
- salience
- recency

Reuse existing ORM tables where possible.

## Non-negotiable rule 6 — memory is not raw history

Use structured memory classes:

- episodic
- semantic
- preference
- project
- procedural
- entity

Retrieval scoring should combine:

- semantic similarity
- entity overlap
- project relevance
- importance
- recency
- confidence

Do not dump the entire conversation into every prompt.

## Non-negotiable rule 7 — context precedence

Use strict context priority:

Tier 0: runtime/system policy
Tier 1: latest user request + active entity + active artifact + workspace selection
Tier 2: recent turns
Tier 3: relevant memories
Tier 4: relevant project/files
Tier 5: compressed older history

Never drop Tier 1 before lower-priority context.

Track approximate/real token budget by section.

## Non-negotiable rule 8 — capability registry

Do not build 1,000 `if` statements.

Every executable ability must become a capability manifest with:

```text
id
version
title
description
parameter schema
result schema
tags
risk level
confirmation requirement
progress support
cancel support
handler
```

Examples:

```text
web.search
image.search
image.generate
image.edit
document.generate
pdf.generate
code.read
code.modify
code.run
build.run
test.run
project.create
project.preview
video.transcribe
video.subtitle
video.render
artifact.save
calendar.create
reminder.create
```

## Non-negotiable rule 9 — capability retrieval at scale

When the registry grows, do not inject every capability into the planner.

Use metadata retrieval:

```text
user request
→ capability search
→ top relevant candidates
→ planner sees only candidate schemas
```

Make the retrieval layer replaceable so lexical retrieval can later become embedding/hybrid retrieval without changing planner contracts.

## Non-negotiable rule 10 — structured planner

Planner output must be schema-constrained.

A plan contains:

```text
goal
steps[]
  id
  capabilityId
  dependencies[]
  arguments
  verification rule
  canParallelize
```

Do not parse execution plans from arbitrary prose.

Do not expose hidden reasoning. A concise public plan is enough.

## Non-negotiable rule 11 — dependency DAG

Independent steps may run concurrently.

Example:

```text
Generate hero image ─┐
                     ├→ Compose website → Build → Preview
Generate copy ───────┘
```

Do not serialize everything unnecessarily.

Detect cycles/unresolved dependencies before execution.

## Non-negotiable rule 12 — tool execution boundary

Never execute model prose directly.

Required:

```text
model/tool proposal
→ structured args
→ schema validation
→ permission gate
→ executor
```

No `eval(model_output)`.

No direct free-form shell from assistant prose.

## Non-negotiable rule 13 — permission levels

Support at least:

```text
LOCAL
READ_ONLY
REVERSIBLE
EXTERNAL_MUTATION
DESTRUCTIVE
```

Safe/local reads can run automatically according to current Hina policy.

Consequential external/destructive operations require appropriate confirmation.

Preserve existing Hina authorization rules.

## Non-negotiable rule 14 — normalized observations

Tools must not dump huge unstructured payloads into the next model call when a normalized result can be produced.

Example build observation:

```json
{
  "status": "failed",
  "exitCode": 1,
  "facts": [
    {
      "type": "typescript_error",
      "file": "src/Hero.tsx",
      "line": 48,
      "message": "..."
    }
  ]
}
```

Preserve raw output for logs/debugging where appropriate, but planning/recovery should operate on normalized observations.

## Non-negotiable rule 15 — verification decides success

HTTP 200 is not enough.

Examples:

- generated image: artifact exists and is loadable
- PDF: output exists and parses/opens
- code edit: expected patch exists
- website: build succeeds
- tests: exit code is zero
- preview: health endpoint or preview runtime is ready
- deployment: endpoint resolves

Create a verifier registry.

Every production capability should have a suitable verifier or explicit default contract.

## Non-negotiable rule 16 — bounded repair

Recoverable errors may trigger a repair strategy.

Example:

```text
code edit
→ build
→ TypeScript error
→ inspect error
→ repair diff
→ rebuild
→ verify
```

Hard maximum repair attempts.

Do not create infinite autonomous loops.

Record every repair attempt in run telemetry.

## Non-negotiable rule 17 — durable objects

Every actionable UI/result should map to a Hina object with stable identity.

Object states:

```text
suggested
draft
ready
queued
running
waiting
requires_input
requires_confirmation
completed
failed
cancelled
archived
```

An image generation request must remain the same object while it moves:

```text
suggestion
→ configuration
→ generating
→ artifact
→ history
→ image workspace
```

Do not replace it with unrelated spinner/result components.

## Non-negotiable rule 18 — artifacts first

Substantial outputs become persistent artifacts.

Minimum artifact types:

```text
image
video
audio
document
pdf
spreadsheet
code
archive
dataset
presentation
website
preview
diff
```

Artifact must track:

- ID
- kind
- MIME
- URI/storage reference
- metadata
- parent object
- version
- created time

## Non-negotiable rule 19 — artifact graph

Track relationships.

Example:

```text
Landing Page
├─ Hero Image
├─ Logo
├─ Copy Document
├─ Hero Component
└─ Preview Deployment
```

This is required for follow-up requests such as:

```text
use the previous image
undo the hero change
regenerate that asset
open the document we just made
```

## Non-negotiable rule 20 — composer must remain normal chat

Do not trap text in action cards.

While typing:

```text
generate a cinematic hero image for Hina|
```

The text remains visible and editable.

Optional suggestion may appear below the composer seam:

```text
✦ Generate image
  Cinematic hero
  Tab to configure
```

User can:

- keep typing
- ignore suggestion
- send normally
- adopt suggestion

Send must always work.

The suggestion system is an optimization, not the only execution path.

## Non-negotiable rule 21 — no model call per keystroke

Local parser first.

For uncertain suggestions, wait for typing idle before remote semantic interpretation.

Target local suggestion latency should feel immediate.

Cancel stale parse requests.

Old interpretation must never overwrite new composer state.

## Non-negotiable rule 22 — preserve The Walk

Use the existing Hina motion constitution:

ONE OBJECT.
FIVE MOTIONS.
CHAT STAYS CALM.
ACTIONS WALK.

Motion primitives:

- tick
- spring
- stagger
- settle
- pulse

Centralize constants.

Do not add a second animation library.

Use `layout/layoutId` or FLIP for structural size/position changes.

Do not manually tween CSS height/width with JS.

Do not animate every chat bubble.

## Non-negotiable rule 23 — honest image generation surface

When user sends:

```text
generate a cinematic hero image for Hina
```

Hina should produce a real image object.

Before execution:

```text
IMAGE
Prompt: ...
Aspect ratio: ...
Generate
```

During actual execution:

```text
IMAGE
Generating image…
Working · 8s
Cancel
```

Only show provider stages that truly exist.

After artifact is verified:

```text
IMAGE
[actual image]
Edit
Variation
Regenerate
Use in project
Open workspace
```

Only show controls that are actually wired to capabilities.

If reference pack bridge returns `not_executed_by_reference_pack`, replace it with the existing real Hina image handler before calling the feature production-ready.

## Non-negotiable rule 24 — workspace promotion

Complex tasks should open a persistent workspace.

### Code workspace

Desktop target:

```text
┌─────────────┬──────────────────────────┬──────────────────────┐
│ FILES       │ CODE / HINA              │ LIVE PREVIEW         │
│             │                          │                      │
│ src         │ Hero.tsx                 │ rendered app         │
│ assets      │                          │                      │
│ components  │ function Hero() { ... }  │                      │
├─────────────┴──────────────────────────┴──────────────────────┤
│ Problems │ Terminal │ Tests │ Changes │ Jobs │ Network       │
└───────────────────────────────────────────────────────────────┘
```

### Image workspace

- prompt/reference editor
- canvas
- versions
- generation jobs
- edit actions

### Document workspace

- structured editor
- page preview
- sources
- export
- versions

Use one workspace architecture with specialized panes. Do not build unrelated applications.

## Non-negotiable rule 25 — real code preview

Do not copy `document.documentElement.outerHTML`.

Use the real project/runtime architecture available in Hina:

```text
workspace files
→ build/bundler/dev server
→ sandboxed preview URL
→ iframe
```

Generated project code must not execute directly inside Hina's own DOM.

If current infrastructure supports HMR, use it.

If not, use reliable incremental rebuild + preview refresh.

## Non-negotiable rule 26 — preview/source selection

When architecture permits, implement bidirectional mapping:

```text
preview selection
→ component/source reference
→ editor selection
```

and:

```text
editor selection
→ optional preview highlight
```

Then commands such as:

```text
make this button larger
make this section bolder
```

resolve against selected source/preview context.

Do not fake this mapping if source metadata does not yet exist. Mark it as a later wired phase and preserve the contract.

## Non-negotiable rule 27 — ChangeSets

Every substantial coding operation creates a ChangeSet:

```text
id
request
files changed
patch/diff
build before/after
tests
preview status
timestamp
```

Expose:

- Review
- Compare
- Accept
- Revert

Do not silently overwrite a large project without traceability.

## Non-negotiable rule 28 — long-running jobs

Image/video/build/indexing jobs can outlive the request.

Use durable run/job IDs.

The browser should be able to reconnect to job state after reload when backend infrastructure supports it.

Do not keep heavy video encoding inside a short-lived Vercel request if current architecture has a worker/sidecar path.

## Non-negotiable rule 29 — cancellation

If provider supports cancellation, wire actual cancel.

If provider cannot cancel after submission, say that honestly.

Do not change UI to `cancelled` while the backend is still actively producing side effects unless cancellation semantics justify it.

## Non-negotiable rule 30 — model router

Reuse Hina's current providers behind a model gateway.

Route by:

- task class
- modality
- latency target
- context requirements
- structured output capability
- tool-use capability
- cost policy already defined by Hina

Do not hardwire core business logic to one vendor/model string.

## Non-negotiable rule 31 — structured outputs

For routing/planning/tool args, use provider structured output/tool calling where available.

Validate schemas.

On invalid output:

- repair structured output, or
- retry within limits, or
- fall back honestly

Do not regex arbitrary markdown JSON as the primary production contract.

## Non-negotiable rule 32 — persistence

Map Astra data onto current persistence architecture.

Persist at least what Hina needs to recover:

- run state
- step/tool state
- object state
- artifacts
- artifact edges
- workspace identity
- relevant ChangeSets
- entity state
- durable memories

Do not duplicate tables that already exist under different names.

Use migrations.

## Non-negotiable rule 33 — traceability

Correlate:

```text
request_id
turn_id
run_id
step_id
call_id
object_id
artifact_id
```

A production issue must be traceable from user turn to exact tool/artifact.

## Non-negotiable rule 34 — observability

Measure real timings:

- context compilation
- entity resolution
- memory retrieval
- route selection
- planning
- tool execution
- verification
- first response token
- total run duration

Do not fabricate performance claims.

## Non-negotiable rule 35 — security

Preserve and strengthen:

- generated code sandbox
- tool parameter validation
- file path restrictions
- URL validation
- secret boundaries
- external-mutation confirmation
- prompt-injection isolation for retrieved content
- authentication and authorization

Retrieved web/file/repository content is untrusted data, not runtime policy.

## Integration sequence

Execute in controlled phases.

### P0 — Audit and tests

- Establish baseline build/test/lint/typecheck.
- Record current production functionality.
- Map reference pack to existing Hina modules.

### P1 — Semantic event stream

- Add event protocol.
- Shadow current chat path if needed.
- Confirm normal chat still streams correctly.

### P2 — Context/entity brain

- Integrate global entity resolver.
- Integrate context compiler.
- Add Mikasa regression test.

### P3 — Memory

- Wire current DB memory models into compiler.
- Add ranked retrieval.

### P4 — Capability registry/router

- Wrap current Hina tools.
- Keep existing tool handlers; do not reimplement working provider logic.

### P5 — Executor/observer/verifier

- Normalize outputs.
- Add verification.
- Add permission boundary.

### P6 — Planner and bounded repair

- Structured plan.
- DAG execution.
- Repair limits.

### P7 — Universal Hina objects

- Backend object state.
- Frontend reducer.
- Same identity through lifecycle.

### P8 — Composer suggestions

- Suggestions while typing.
- Normal Send preserved.
- no LLM-per-keystroke.

### P9 — Image integration

- Replace reference image bridge with real Hina image provider.
- Honest generation telemetry.
- Artifact persistence.
- Versions/deeper controls.

### P10 — Document integration

- Existing document pipeline becomes capability/object/artifact.

### P11 — Code workspace

- Source editor.
- File tree.
- real sandboxed preview.
- build/test telemetry.
- ChangeSets.

### P12 — Deeper workspaces

- image
- document
- research/data/media as current Hina capability allows.

### P13 — scale + performance

- capability retrieval
- virtualization where needed
- worker/sidecar integration
- profiling

### P14 — micro-polish

- final motion polish only after runtime correctness.

## Mandatory test matrix

### Normal chat

Input:

```text
hey hina
```

Expected:

- CHAT route
- no unnecessary action surface
- normal response stream

### Entity continuity

Input sequence:

```text
Who is Mikasa Ackerman?
tell me more about her
show me images
```

Expected:

- active subject is Mikasa Ackerman
- `her` resolves correctly
- image query is entity-grounded
- previous prose is never used as canonical image query

### Composer

Type:

```text
generate an image of Hina in Tokyo at night
```

Expected while typing:

- text remains visible
- focus remains in textarea
- optional suggestion appears
- Send still works

### Image execution

After Send:

- real image capability starts
- object state becomes running
- honest status appears
- no fake percentage
- final real artifact attaches to same object
- failure remains attached to same object

### Split local action

Input:

```text
split 2400 between 3
```

Expected:

- direct action
- result = 800 each
- no remote model required for arithmetic

### Project/workspace

Input:

```text
build a premium Hina landing page
```

Expected:

- WORKSPACE route
- project/workspace object created
- source files exist
- build is executed
- build output is real
- preview is an actual sandbox/dev-server URL
- failure is never reported as success

### Build recovery

Introduce a controlled TypeScript error.

Expected:

- `build.run` fails
- normalized error observation exists
- bounded repair may execute
- build reruns
- success only after verification

### Permissions

Trigger a capability marked external mutation.

Expected:

- execution pauses for confirmation according to Hina policy
- no side effect before approval

### Reduced motion

Expected:

- same functionality
- instant/subtle state transitions
- no forced loops or large movement

## Performance requirements

- Typing must not rerender the entire conversation/workspace.
- Local composer suggestions should feel immediate.
- Cancel stale semantic parsing.
- Do not run remote model calls per keystroke.
- Avoid per-frame React state.
- Structural movement uses layout/FLIP.
- Profile before claiming 60fps.

## Production completion rule

Do not say "fully integrated" until all of these are true:

1. Actual Hina source files were modified.
2. Existing handlers are wired into Astra capabilities.
3. Normal chat works.
4. Entity regression works.
5. Image generation uses the real provider.
6. Document generation uses the real pipeline.
7. Semantic events are visible in the real UI.
8. Composer text/focus are preserved.
9. Objects preserve identity.
10. Real build/typecheck/lint/tests pass.
11. Production build passes.
12. No mock/fake progress remains on enabled features.
13. No placeholder bridge is presented as real execution.
14. Security boundaries remain intact.

## Final engineering report required

When implementation is finished, provide:

- baseline architecture discovered
- final architecture
- files created
- files modified
- migrations added
- existing systems reused
- capabilities wired
- model adapters wired
- event protocol implementation
- UI integration details
- tests added
- exact test results
- exact typecheck result
- exact lint result
- exact production build result
- known limitations
- disabled/unwired capabilities
- deployment/branch/commit information if you actually performed them

Never fabricate deployment, commit, test, or build results.

Final law:

```text
HINA IS NOT LLM + UI.

HINA ASTRA =
PERCEPTION
+ CONTEXT
+ MEMORY
+ ENTITIES
+ ROUTING
+ CAPABILITIES
+ PLANNING
+ PERMISSIONS
+ EXECUTION
+ OBSERVATION
+ VERIFICATION
+ REPAIR
+ ARTIFACTS
+ WORKSPACES
+ CONVERSATION.
```

Integrate incrementally. Preserve working Hina behavior. Validate every phase. Ship only what is real.
