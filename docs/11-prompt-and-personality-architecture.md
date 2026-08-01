# Prompt and personality architecture

## Purpose

Prevent one unmaintainable prompt and constrain personality, mood, memory, vision, and performance output.

## Decision

Prompt assembly is deterministic and ordered:

1. immutable safety/privacy;
2. product behavior and AI identity transparency;
3. selected companion identity;
4. Nepali/mixed-language style;
5. bounded user personality settings;
6. bounded mood snapshot;
7. conversation context;
8. approved retrieved memories with IDs;
9. untrusted vision/retrieval/tool data in delimited data blocks;
10. tool policy/permissions (tools disabled in MVP);
11. response JSON schema and allowlists.

Production prompt text will be versioned with a content hash and evaluated before promotion. The model returns `AssistantTurnPlan`; Pydantic/JSON Schema validation rejects additional properties and values outside allowlists. On first failure, retry once with schema-only correction and no new user data; then use a neutral text plan.

Companion profiles differ in wording/style examples, not policy. Settings are normalized 0–1 and clamped server-side: affection <=0.8, sass <=0.7, energy <=0.9, humor <=0.8, proactivity <=0.6 for MVP defaults; teasing cannot target protected/sensitive traits, distress, appearance, competence or abandonment.

### Files

Specifications live in [prompts](prompts/README.md): female/male identity, performance planner, memory extractor, summarizer, tool planner, vision interpretation, Nepali style and error recovery. They define inputs, outputs and tests rather than claiming final production wording.

**Runtime (Tier A):** deterministic assembly is implemented in `apps/api/hinaa_api/prompts/` and documented in [TIER-A-RUNTIME.md](prompts/TIER-A-RUNTIME.md). Spec Markdown remains design intent; Python layers are the executable source of truth for current builds.

### Injection tests

Test indirect instructions in web/file/camera/tool/memory content; fake system tags; Unicode/encoding; requests for secrets; schema breakout; filename/bone/tool injection; memory poisoning; multilingual jailbreak; and instruction conflicts. Expected behavior is ignore hostile instruction, preserve relevant data, explain refusal only when useful, and never escalate privilege.

## Alternatives considered

One giant prompt is hard to test; client-side prompt assembly exposes policy and enables tampering; unconstrained free text makes avatar/tool behavior unsafe.

## Reasoning

Layering supports targeted regression tests and separates character creativity from immutable controls.

## Risks

Schemas do not prevent harmful natural language and prompt versions can regress Nepali style. Add content-policy tests, human review and canary evaluation.

## Acceptance criteria

- Every generated plan validates or falls back safely.
- Changing companion profile cannot alter policy/tool permission.
- Injection corpus has 100% prevention of secret/tool/bone execution attempts.
- Nepali evaluators rate language fit separately from safety.

