# Mobile UX and design system

## Purpose

Specify an achievable, accessible mobile interface and all required wireframes.

## Decision

Use token-based CSS (Tailwind may consume the tokens) with semantic colors for idle/listening/thinking/speaking/error, 8 px spacing grid, 12/16/20/28 type scale, minimum 44×44 CSS px targets, visible focus, AA contrast, reduced-motion, screen-reader live regions, and `env(safe-area-inset-*)`. Never encode state by color alone.

### Main screen wireframe

```text
┌ status: Listening…  provider ●  settings ┐
│                                           │
│              3D avatar                    │
│       (portrait/text fallback here)       │
│                                           │
│ companion switch        camera OFF        │
├ expandable transcript/chat sheet ─────────┤
│ partial transcript…                       │
│ [type a message…]                 [send]  │
└ [stop]            [ large mic ]            ┘
```

Mic is thumb-reachable; stop replaces/sits beside it while speaking. Camera always displays off/on state. Keyboard raises the chat sheet without covering send. Landscape uses avatar left/chat right; tablets cap reading width.

### Screen specifications

- **Onboarding:** value, AI disclosure, language, companion preview, “continue”; no sensor request.
- **Permission explanation:** purpose, what leaves device, duration, “not now”, then OS prompt just in time.
- **Main:** wireframe above, state text, provider/offline indicator, avatar quality fallback.
- **Text chat sheet:** partial/final labels, edit before send where possible, timestamps, retry, memory candidate chip.
- **Voice settings:** voice profile, speed 0.8–1.2, test with non-sensitive sample, input language/auto-detect, echo advice.
- **Character selection:** licensed thumbnails, female/male profile, download size, active check.
- **Memory manager:** disabled/private toggle, list/source/date, edit/forget, delete-all with destructive confirmation.
- **Provider settings:** current route, health/cost/privacy labels, fallback consent; IDs advanced-only.
- **BYOK:** post-MVP badge, masked keys, test/rotate/revoke/delete; never display recovered secret.
- **Privacy dashboard:** mic/camera/memory consent log, export/delete, retention summary.
- **Error/offline:** cause, preserved work, retry/text/mock actions; no raw provider error.

3D canvas is `aria-hidden`; equivalent state and transcript are DOM. Screen-reader announcements are polite for partial text, assertive only for permission/error/interruption. Reduced motion disables micro-gaze/spring/large gestures but retains static expressions/state labels. Text-only is persistent, not an error mode.

## Alternatives considered

Desktop-first panels and gesture-only controls fail small screens/accessibility. Immediate permission prompts reduce trust.

## Reasoning

The avatar remains the visual focus while critical actions and privacy state stay ordinary accessible controls.

## Risks

Bottom sheets, virtual keyboards and WebGL compete for viewport/GPU. Test 320×568 through tablets, dynamic viewport units, portrait/landscape and low-memory kill/reload.

## Acceptance criteria

- WCAG 2.2 AA automated checks plus manual keyboard/screen-reader flow.
- All targets >=44×44; safe-area and keyboard tests pass.
- Full text conversation works with canvas disabled.
- Camera cannot be visually ambiguous.

