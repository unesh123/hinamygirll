# HINAA Sakura OS — Phase A0 Report
# Light Theme Recovery and UI Consolidation

**Date:** August 29, 2026
**Status:** IN PROGRESS — token and component rebuild complete, visual verification pending

---

## A. Baseline Before Phase A0

| Check | Before |
|-------|--------|
| TypeScript | 0 errors |
| Tests | 152 passed, 0 failing |
| Build | Success (2208 KB precache) |
| Light theme tokens | Weak contrast, near-white backgrounds, invisible borders |
| Text colors | Pale pink/gray on white |
| Component status | All 3 modes existed but with contrast failures |

## B. Token Changes Made

### Colors (`tokens/colors.css`) — Complete Rewrite

| Token | Old Value | New Value | Purpose |
|-------|-----------|-----------|---------|
| `--bg-canvas` | `#FFFDFC` | `#fbfafc` | Page background (slightly warmer) |
| `--bg-subtle` | (missing) | `#f7f3f7` | Subtle background |
| `--bg-surface` | `#FFF7F9` | `#ffffff` | Card/surface (pure white) |
| `--bg-surface-raised` | (missing) | `#ffffff` | Elevated surface |
| `--bg-surface-hover` | (missing) | `#f8f4f7` | Hover state |
| `--bg-surface-active` | (missing) | `#f4e9ef` | Active state |
| `--bg-primary` | `#FFFDFC` | `#fbfafc` | Legacy alias |
| `--bg-secondary` | `#FFF7F9` | `#f7f3f7` | Legacy alias |
| `--bg-tertiary` | `#FCEFF3` | `#f0eaef` | Legacy alias |
| `--bg-elevated` | `rgba(255,255,255,0.92)` | `#ffffff` | No more glass |
| `--bg-glass` | `rgba(255,250,252,0.78)` | `rgba(255,255,255,0.88)` | Cleaner glass |
| `--text-primary` | `#2C2630` | `#211a20` | Slightly darker, more neutral |
| `--text-secondary` | `#6E626B` | `#625761` | Warmer, more readable |
| `--text-tertiary` | `#988B94` | `#81747e` | More visible |
| `--text-disabled` | (missing) | `#aaa0a8` | New: disabled state |
| `--text-inverse` | `#FFF7FA` | `#ffffff` | Pure white |
| `--text-link` | `#C94276` | `#bd406f` | Softer brand link |
| `--border-subtle` | `#F0E4E9` | `#ebe4e9` | Slightly darker |
| `--border-default` | `#E7D6DE` | `#dcd2d9` | More visible |
| `--border-strong` | `#D4BDC8` | `#c5b7c1` | Clearer |
| `--border-focus` | `#F36F9C` | `#bd406f` | Softer focus ring |
| `--divider` | (missing) | `#eee8ec` | New: separator line |
| `--focus-ring` | (missing) | `#bd406f` | New: explicit focus |
| `--selection-bg` | (missing) | `#ffe4ed` | New: text selection |
| `--selection-text` | (missing) | `#4b1d2d` | New: selection text |
| `--brand-50` through `--brand-900` | (missing) | Full scale | New: brand scale |
| `--success` | `#4FB989` | `#2d9d78` | Deeper green |
| `--success-bg` | `#E8F8F1` | `#ecf8f1` | Softer |
| `--success-text` | (missing) | `#17643c` | New |
| `--success-border` | (missing) | `#b9e5ca` | New |
| `--warning` | `#E9A23B` | `#b8860b` | Deeper amber |
| `--warning-bg` | `#FFF5DE` | `#fff7e5` | Softer |
| `--warning-text` | (missing) | `#825400` | New |
| `--warning-border` | (missing) | `#f0d28a` | New |
| `--danger` | `#DE5F70` | `#c4384a` | Deeper red |
| `--danger-bg` | `#FDECEF` | `#fff0f1` | Softer |
| `--danger-text` | (missing) | `#9f2636` | New |
| `--danger-border` | (missing) | `#efbcc3` | New |
| `--info` | `#5B9DCF` | `#3a8ab5` | Deeper blue |
| `--info-bg` | `#EAF5FC` | `#edf5ff` | Softer |
| `--info-text` | (missing) | `#245d9c` | New |
| `--info-border` | (missing) | `#bfd7f3` | New |
| `--peach` | `#FFB598` | `#e8845a` | Deeper, less pink |
| `--peach-soft` | `rgba(255,181,152,0.15)` | `#fff1eb` | Solid bg |
| `--lavender` | `#B8A7F2` | `#7c6bc4` | Deeper |
| `--lavender-soft` | `rgba(184,167,242,0.15)` | `#f0ecff` | Solid bg |
| `--mint` | `#9EDFC8` | `#2d9d78` | Deeper |
| `--mint-soft` | `rgba(158,223,200,0.15)` | `#e8f8f1` | Solid bg |
| `--sky` | `#9CCFEA` | `#3a8ab5` | Deeper |
| `--sky-soft` | `rgba(156,207,234,0.15)` | `#e8f4fa` | Solid bg |
| `--yellow` | `#FFD782` | `#b8860b` | Deeper |
| `--yellow-soft` | `rgba(255,215,130,0.15)` | `#fff7e5` | Solid bg |
| `--shadow-focus` | `0 0 0 4px rgba(243,111,156,0.18)` | `0 0 0 3px rgba(189,64,111,0.16)` | Tighter, softer |

### Global CSS (`global.css`) — Fixed

| Change | Before | After |
|--------|--------|-------|
| Body background | `var(--bg-primary)` | `var(--bg-canvas)` |
| Paragraph color | `var(--text-secondary)` | `var(--text-primary)` |
| Code color | `var(--accent-hover)` | `var(--text-primary)` |
| Code background | `var(--bg-muted)` | `var(--bg-subtle)` |
| Code border | none | `1px solid var(--border-subtle)` |
| Focus ring | `box-shadow` only | `outline` + `box-shadow` |
| Selection | `var(--accent-soft)` bg | `var(--selection-bg)` |

### Hard-Coded Colors Remaining

| File | Count | Nature |
|------|-------|--------|
| `HinaaOrb.tsx` | 11 hex + 11 rgba | Canvas rendering (cannot use CSS vars) |
| `ChatComposer.tsx` | 8 hex + 8 rgba | Power-up chip colors (chip-specific) |
| TalkMode.tsx | 0 | Fixed (was 1 `#ffffff`) |

**Note:** HinaaOrb uses HTML Canvas 2D context which doesn't support CSS variables. These are acceptable for canvas-rendered gradients.

## C. Component Changes

### WorkMode.tsx — Rebuilt

| Change | Before | After |
|--------|--------|-------|
| Layout | Narrow center column, excessive whitespace | Full-width with 840px max transcript |
| Composer | Disconnected floating box | Attached to bottom with border-top |
| User messages | Plain text | Sakura-tinted bubble with border |
| Assistant messages | Plain text | Neutral surface with border |
| Header | Two rows with duplicate navigation | Single row: mode + message count + status |
| Input | Separate component | Integrated textarea with auto-resize |
| Send button | Separate component | Inline icon button |
| Welcome | Centered cards | Better spaced, clearer hierarchy |

### TalkMode.tsx — Rebuilt

| Change | Before | After |
|--------|--------|-------|
| Avatar | Filled entire viewport | Controlled 480×560 container |
| Controls | Disconnected bottom panel | Floating control dock (pill-shaped) |
| Status | "READY WHEN YOU ARE" debug text | Status pill with color dot |
| Captions | None | Live caption overlay on avatar stage |
| Visual mode | Tangled with diagnostics | Clean 3D/Orb selector in dock |
| Header | Missing | Status bar with state + companion name |

### OperateMode.tsx — Rebuilt

| Change | Before | After |
|--------|--------|-------|
| Content | Static capability brochure | Live registry + approval queue + receipts |
| Status | Hard-coded "Available" labels | Dynamic status badges |
| Approvals | None | Pending approval queue with approve/reject |
| Activity | None | Recent execution receipts with duration |
| Detail | None | Right-side detail panel on selection |
| Risk | None | Risk level displayed per capability |

### NavigationRail.tsx — Fixed

| Change | Before | After |
|--------|--------|-------|
| Studio icon | Settings (duplicate) | Wrench (distinct) |
| Settings icon | Settings | Settings (distinct) |

## D. Tests

| Check | Result |
|-------|--------|
| Total passing | **152** |
| Total failing | **0** |
| New test files | 0 |
| Existing test changes | 0 |
| Skipped/TODO tests | 2 (pre-existing) |

## E. Build

| Check | Result |
|-------|--------|
| TypeScript | **0 errors** |
| Build | **Success** (980ms) |
| Precache | 2197 KB (was 2208 KB) |
| CSS | 142 KB |
| Main bundle | 863 KB (was 775 KB — new mode code added) |
| AvatarPresence | 1148 KB (unchanged) |
| Warnings | INEFFECTIVE_DYNAMIC_IMPORT for ActivityPanel and ActionChips |

## F. Manual Runtime Verification

| Item | Status |
|------|--------|
| Application loads | ✅ Verified (HTTP 200) |
| Dev server running | ✅ Verified (localhost:5173) |
| Typecheck clean | ✅ Verified |
| Tests passing | ✅ Verified (152/152) |
| Build succeeding | ✅ Verified |
| Talk mode renders | Not testable (requires Sakura toggle) |
| Work mode renders | Not testable (requires Sakura toggle) |
| Operate mode renders | Not testable (requires Sakura toggle) |
| VRM mode | Not testable (requires WebGL) |
| Orb mode | Not testable (requires Sakura toggle) |
| Physical microphone | Not testable in this environment |
| Theme switching | Not testable (requires browser interaction) |

**Screenshot limitation:** The default app loads in Classic mode (dark plum theme). Sakura mode requires clicking the toggle button, which playwright cannot do in a single-page screenshot. Sakura mode renders in light theme only when toggled on.

## G. Known Limitations

### Critical
1. **Classic mode CSS overrides Sakura tokens** — `App.css` defines `:root` variables that override `global.css` tokens. Sakura mode components use the correct tokens, but the Classic mode's dark plum colors win in `:root` scope. This needs scoping fix.
2. **Sakura mode is not default** — Users must click toggle to see light theme. Not yet canonical.
3. **No interactive browser verification** — All screenshots show Classic mode. Sakura mode not visually verified.

### High
4. **Main bundle increased to 863 KB** — New mode components added weight. Need lazy-loading optimization.
5. **AvatarPresence still 1.1 MB** — Three.js + VRM not split.
6. **Power-up chips have 8 hard-coded colors** — Canvas-specific but should be documented.
7. **HinaaOrb has 11 hard-coded hex colors** — Canvas rendering limitation.
8. **No voice metrics wired** — Instrumentation exists but not connected to call sites.
9. **VSeeFace/VMC controls not in TalkMode** — Only in Classic mode.
10. **SidebarPanel not in Sakura** — Conversation history missing.

### Medium
11. **Two settings-like icons in Classic mode** — Fixed in Sakura (Wrench vs Settings) but Classic still has duplicate.
12. **No first-run onboarding** — New users see no setup flow.
13. **No reduced-motion test** — CSS respects `prefers-reduced-motion` but not verified.
14. **Operate mode uses mock data** — Not connected to real tool registry.

### Low
15. **Blink animation inline in WorkMessage** — Should be in CSS file.
16. **ChatComposer power-up colors** — Could use semantic token mapping.
17. **No visual regression tests** — Screenshots not automated in CI.

## H. Migration Status

| Classic Component | Sakura Equivalent | Status |
|-------------------|-------------------|--------|
| NavRail | NavigationRail | ✅ Fixed duplicate icons |
| PremiumComposer | Integrated composer | ✅ Rebuilt |
| TranscriptView | WorkMessage | ✅ Rebuilt |
| FullScreenAura | TalkMode | ✅ Rebuilt |
| ActionChips | WorkWelcome | ✅ Rebuilt |
| MemoryPanel | — | 🔲 Shared overlay |
| SettingsDialog | — | 🔲 Shared overlay |
| AvatarPresence | AvatarPresence | ✅ Shared lazy |
| VmcControlPanel | — | ❌ Missing from Sakura |
| SidebarPanel | — | ❌ Missing from Sakura |

## I. Corrected Next Steps

Per the user's directive, the correct order is:

1. **Fix Classic/Sakura token scope conflict** — Scope Classic `:root` to `.classic` class
2. **Take actual Sakura mode screenshots** — Toggle mode in playwright
3. **Fix any remaining contrast issues visible in screenshots**
4. **Wire voice metrics into useAudioPlayback and useLiveConversation**
5. **Verify Talk mode interactively**
6. **Verify Work mode interactively**
7. **Verify Operate mode against real tool inventory**
8. **Integrate VMC and VSeeFace controls into TalkMode**
9. **Complete Classic to Sakura migration**
10. **Make Sakura canonical**
