# HINAA Product Design System

## Product design read

HINAA is a **private companion and capable local agent**, not a generic dashboard, developer console, or marketing page. Her interface should feel composed, quiet, responsive, and intimate without hiding the operational truth of voice, VSeeFace, local tools, or image generation. The design is therefore an **ink-and-rose companion workspace**: dark plum-neutral surfaces, soft rose as the sole product accent, warm ivory typography, and semantic colors reserved only for actual ready, warning, and failure states.

This document applies the audit-first, single-accent, single-theme, contrast-first, motion-with-purpose guidance in Taste Skill and Impeccable.[1] [2] It uses 21st.dev as a source of compatible React interaction patterns, not as a runtime dependency or a source of unreviewed copied code.[3]

## Immutable visual decisions

| System | Decision | Reason |
|---|---|---|
| Theme | One dark **Ink Rose** theme across the assistant, VMC, image studio, and side panels. | The existing dark navy/teal drawer in the supplied screenshot does not match HINAA’s rose-toned character presentation. |
| Product accent | `#EE91AD` rose, with lighter `#FFD6E1` for emphasis. | Gives HINAA a recognisable, character-aligned accent without generic purple/blue AI gradients. |
| Semantic status | Green only for true fresh external connection, amber for waiting/stale, red for failure, rose for primary actions. | Status color must convey state rather than decorate every component. |
| Surfaces | Tinted near-black plum, translucent mica panels, one subtle inner highlight, and a low-opacity grain/noise layer. | Creates depth without heavy card nesting, sharp blue borders, or false 3D chrome. |
| Typography | `Outfit` for display and body, `JetBrains Mono` only for metrics/ports/timestamps. | Separates intimate conversational content from technical diagnostics while avoiding default Inter styling. |
| Shape language | 18px containers, 12px controls, 8px compact chips. | A consistent soft-but-precise hierarchy. |
| Motion | 120–220ms pressed/hover feedback; 180–280ms panels; transform/opacity only; reduced-motion fallback. | Feels responsive without slow decorative animation or layout shift. |

## Interaction architecture

The agent workspace remains anchored by a single HINAA stage and one composer. Contextual work opens in an anchored panel rather than producing competing modal stacks. The VSeeFace control should use **progressive disclosure**: one visible action, then a simple three-step readiness progression, with advanced channels and raw transport data behind an expandable diagnostic section.

| Surface | Primary purpose | Selected compatible pattern | Explicitly avoided |
|---|---|---|---|
| Companion stage | Establish presence, voice state, and focused conversation. | Soft spotlight edge, presence halo, unobtrusive one-tap playground action. | A second avatar canvas, full-body dashboard framing, or animated status clutter. |
| Composer | Make typing, voice start/stop, image mode, and task mode immediately legible. | High-contrast action rail with press feedback and local status copy. | Floating fake controls, unlabeled icon-only critical actions, or delayed keyboard actions. |
| VSeeFace panel | Connect, confirm, calibrate, and diagnose. | Stepped connection card, semantic readiness line, expandable technical detail. | The dense multi-card metrics wall shown in the supplied screenshot. |
| Image studio | Start an explicit local job and observe sequential output slots. | Asymmetric controls plus persistent progressive slots, skeletons, and actionable unavailable state. | Decorative generic spinner that hides ComfyUI status or promises results before a local job exists. |
| Agent work | Make research/task progress visible but secondary to conversation. | Compact live run rail with purposeful reveal and interrupt-safe state. | Fake task cards, endless pulsing, or a competing dashboard. |

## Component selection policy

HINAA may use the following patterns inspired by the 21st.dev React/shadcn registry: a shimmer treatment for one primary action, a small command palette, and motion-safe disclosure panels. Each pattern must be implemented using the existing React, Framer Motion, Lucide, and CSS architecture; no component registry package is introduced and no arbitrary third-party code is executed.

> The interface must tell the truth. A local bridge that is only listening is not connected tracking. A model that is streaming text but has not produced audio is not speaking. A ComfyUI service that is unavailable is not an image-generation result.

## Design acceptance checklist

The implementation is ready only when the companion pane, VMC panel, image studio, and composer share the palette, typography, spacing, focus states, and motion contract above; no default blue/teal control panel remains; panels remain keyboard reachable; and dense diagnostics are progressive rather than the default visual layer.

## References

[1]: https://www.tasteskill.dev/docs "Taste Skill documentation"
[2]: https://github.com/pbakaus/impeccable "Impeccable design guidance"
[3]: https://21st.dev/ "21st.dev React component registry"


## Screenshot-driven workspace correction — 2026-08-13

The supplied desktop screen exposed an incomplete visual migration: a dark Ink Rose shell was surrounding transcript modules, navigation controls, and composer states that still used legacy light-surface, mint/cyan, and dark-text values. The result was low contrast, weak message hierarchy, and an unfinished split-dashboard feel.

The corrective visual target is a **focused companion workspace**, not a generic admin dashboard. The avatar remains a single dedicated left stage with restrained framing and a small presence label; it must not compete with the conversation. The right pane becomes the reading surface: it uses a warm near-black canvas, a narrow readable text measure, clearly separated assistant and user message surfaces, substantial vertical rhythm, and high-contrast text. The composer is elevated as the main action surface with one clear rose send action and quiet secondary tools. The compact rail uses plum glass, a single rose active state, and no leftover cyan/mint gradients.

| Surface | Corrected target |
|---|---|
| Avatar stage | Stable 34–38% desktop width, dark cinematic vignette, compact top presence chip, clear model controls in a low-profile dock. |
| Conversation | High-contrast assistant text on a subtle document surface; user turns use a deeper rose, not a pale cyan capsule. |
| Composer | Opaque/tinted elevated input tray with readable placeholder, grouped quiet controls, one distinctive send button, and keyboard focus glow. |
| Header and rail | Fewer but stronger visual anchors, 1 px low-contrast separators, semantic live green only for verified status, no competing rainbow accents. |
| Motion | 120–220 ms transform/opacity interactions; no layout-shifting decorative animation; reduced-motion support preserved. |
