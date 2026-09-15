# HINAA Product V6 — Comprehensive UI/UX & Architecture Audit

**Date**: September 15, 2026  
**Auditor**: Antigravity Engineering Team  
**Milestone**: HINAA Frontier Product V6  

---

## 1. Executive Summary

This audit evaluates the current frontend implementation of HINAA across 24 core surfaces, analyzing consistency, duplicate systems, dead components, layout hacks, and runtime wiring before beginning the V6 product-completion phase.

While the underlying backend engines (ContextCompiler, durable tasks, topic precedence, SceneSpecification, adaptive depth) are robust, the user interface remains fragmented between legacy experimental components and newer design-system primitives. V6 will unify these systems into **one coherent, visually polished, responsive, and accessible AI workspace**.

---

## 2. Surface-by-Surface Evaluation

| Surface | Status | Findings & Diagnosis | Action for V6 |
|---|---|---|---|
| **1. App Shell** | `PARTIAL` | `AppShell.tsx` provides desktop navigation rail and content stage, but mode switching lacks unified breadcrumb context and header state. | Unify App Shell V6 with responsive 3-pane layout, persistent header context, and companion dock. |
| **2. Talk Mode** | `GOOD` | High-quality VRM and procedural orb rendering with push-to-talk and subtitle overlay. Missing integrated quick text input (requires switching to Work mode). | Add lightweight ambient composer overlay and quick creative interaction controls. |
| **3. Work Mode** | `INCONSISTENT` | Monolithic file (`WorkMode.tsx`, ~1850 lines) managing chat history, activity cards, avatar dock, and composer with inline CSS and duplicated layout logic. | Decompose into modular components: `ChatPane`, `CompanionDock`, `ComposerV6`, `ActivityLedger`. |
| **4. Operate Mode** | `BROKEN` | `OperateMode.tsx` contains a static mock `TOOL_REGISTRY` with non-functional buttons (`desktop_control`, `shell_command`) disconnected from real agent execution. | Rewire to live durable tasks, computer/browser actions, execution logs, and `ApprovalCard` workflows. |
| **5. Composer** | `PARTIAL` | `ComposerV5` successfully introduced action modes and basic topic chips, but lacks Context Chips V2 (click preview, project/repo/asset types), smart `+` menu, and AUTO/FAST/DEEP/MAX selector. | Upgrade to canonical `ComposerV6` with full chip semantics and expandable action menu. |
| **6. Sidebar / Nav** | `DUPLICATE` | Two competing navigation rails exist: `components/ui/NavRail.tsx` (dead) vs `design-system/layout/NavigationRail.tsx`. `ConversationSidebar` lacks search and project filters. | Retire legacy rail. Enhance `ConversationSidebar` with search, project grouping, and active task indicators. |
| **7. Top Navigation** | `PARTIAL` | Plain toggle buttons for `Talk`, `Work`, `Operate`. Lacks active project / active goal / active thread breadcrumbs. | Build TopBar V6 with project pill, active goal chip, and seamless mode tabs preserving exact state. |
| **8. Avatar Docking** | `PARTIAL` | `WorkMode` supports Right, Left, and Floating positions, but lacks `Compact` and `Hidden` states needed to free full-width workspace for coding and documents. | Add `Compact` (pip/mini) and `Hidden` dock modes with persisted user preference. |
| **9. Conversations** | `PARTIAL` | Thread switching occurs backend-side, but UI does not visually expose thread boundaries or provide "Branch from here" actions. | Add conversation branch action, thread switch indicator chip, and search within chat. |
| **10. Context Chips** | `PARTIAL` | Only topic and model chips are supported. Missing PROJECT, REPO, FILE, IMAGE, ARTIFACT, TASK, and GOAL chips. Chips lack click-to-preview popovers. | Implement Context Chips V2 with preview cards and non-destructive removal. |
| **11. Media Galleries** | `INCONSISTENT` | `ChatGPTImageGallery.tsx` and `ChatGPTImagesView.tsx` are unpolished. Lacks explicit asset selection badge (`[Selected · Image 2]`) and quick actions on hover. | Create unified `MediaGalleryV6` separating WEB, NEWS, STOCK, and GENERATED with hover action bar. |
| **12. Tool Cards** | `PARTIAL` | `AgentActivityCard` renders live steps, but lacks the durable coding completion card with changed file list, test counts, and diff toggle. | Add `CodingCompletionCard` and structured tool result envelopes. |
| **13. Artifact UI** | `PARTIAL` | Artifacts rendered as raw code/text blocks in `LocalProjectWorkspace`. Missing dedicated preview cards for Presentations, Documents, Spreadsheets, and Websites. | Build rich typed `ArtifactCard` with slide counts, word counts, charts, and export actions. |
| **14. Sources / Citations** | `PARTIAL` | Inline citations `[1]` are basic anchor tags. No rich hover popover showing publisher, article title, date, and supporting snippet. | Implement `CitationPopover` on hover and an expandable `SourcePanel` listing verified sources. |
| **15. Approvals** | `MISSING` | Approvals for Git operations (commit, push, PR) and consequential tools lack an explicit, high-visibility card. | Build `ApprovalCard` displaying risk level, target files, verification status, and Approve/Reject buttons. |
| **16. Settings** | `INCONSISTENT` | Settings scattered across multiple ad-hoc drawer panels (`ProviderSettings`, `ModelControlBar`, `AvatarLab`). | Create unified, searchable `SettingsV6` (General, Appearance, Voice, Models, Media, Tools, Integrations, Developer). |
| **17. Mobile Layouts** | `PARTIAL` | WorkMode has mobile tabs, but virtual keyboard shifts layout unpredictably. Missing bottom-sheet for advanced composer options. | Implement mobile-first composer sheet, safe-area inset handling, and virtual keyboard stabilization. |
| **18. Loading States** | `PARTIAL` | Infinite spinner on certain long actions. Missing granular states (*Thinking*, *Researching*, *Searching images*, *Verifying*). | Standardize semantic loading badges with elapsed timers and clear activity text. |
| **19. Error States** | `PARTIAL` | Unhandled tool or API failures output plain error text without retry, provider fallback, or repair options. | Implement typed `ErrorCard` with explicit recovery actions (*Retry*, *Switch Provider*, *Broaden Search*). |
| **20. Empty States** | `PARTIAL` | Only the initial chat view has `WelcomeScene`. Empty project, empty artifact library, and empty tasks show blank white/gray panels. | Design purposeful empty state illustrations with quick-start starter action chips. |
| **21. Accessibility** | `PARTIAL` | Missing ARIA live regions for streaming content, focus trap management on drawers, and contrast validation on light themes. | Implement WCAG-compliant contrast tokens, ARIA live regions for streaming, and full keyboard focus outlines. |
| **22. Keyboard Nav** | `PARTIAL` | Textarea handles Enter/Shift+Enter, but lacks global `Cmd/Ctrl+K` command palette and menu arrow navigation. | Implement global Command Palette (`Cmd/Ctrl+K`) for switching chats, running goals, and attaching files. |
| **23. Performance** | `GOOD` | Micro-batching with RAF prevents main thread blocking, but massive 100K-token responses lack block virtualization. | Add block/chunk virtualization for massive assistant responses. |
| **24. Responsive** | `PARTIAL` | Desktop and mobile exist, but tablet (768px-1024px) experiences awkward multi-column squishing. | Implement clean 3-tier responsive breakpoints: Desktop (3-pane), Tablet (2-pane collapsible), Mobile (1-pane + sheet). |

---

## 3. Inventory of Duplicate & Dead Components

### A. Multiple Competing Composers
1. `apps/web/src/components/ui/PremiumComposer.tsx` (Legacy crystal bar — dead code).
2. `apps/web/src/design-system/chat/ChatComposer.tsx` (Intermediate composer).
3. `apps/web/src/design-system/chat/ComposerV5.tsx` (Current active composer).
*Resolution*: Consolidate into canonical `ComposerV6` and deprecate legacy implementations.

### B. Multiple Navigation Rails
1. `apps/web/src/components/ui/NavRail.tsx` (Legacy component).
2. `apps/web/src/design-system/layout/NavigationRail.tsx` (Active canonical component).
*Resolution*: Delete `components/ui/NavRail.tsx`.

### C. Competing Image Studio Views
1. `apps/web/src/components/ui/ChatGPTImagesView.tsx` (Mock inspiration gallery).
2. `apps/web/src/components/ui/LocalImageStudio.tsx` (Partial local canvas).
3. `apps/web/src/components/ui/MagnificImageStudio.tsx` (Active functional studio).
*Resolution*: Retain `MagnificImageStudio` as the primary studio engine and prune mock-only views.

### D. Fragmented Response Renderers
1. `apps/web/src/components/ui/ResponseRenderer.tsx`
2. `apps/web/src/components/ui/ResponseMarkdown.tsx`
3. `apps/web/src/features/chat/components/GenericResultRenderer.tsx`
*Resolution*: Build unified typed `ResponseEnvelope` renderer handling structured payload types without raw Markdown hacks.

---

## 4. Hard-Coded Styles & Layout Hacks Identified
1. Arbitrary inline styles in `WorkMode.tsx` (`style={{ background: "#...", padding: "12px 14px", borderRadius: 8 }}`).
2. Inconsistent color tokens: `#f472b6`, `#eb6f92`, `var(--accent)`, `var(--sakura-500)` mixed arbitrarily.
3. Mobile height calculations relying on `100vh` rather than `100dvh` with safe-area bottom padding.
4. Unbounded textarea growth without max-height constraints on small screens.

---

## 5. Architectural Objectives for Product V6

1. **Design Tokens**: Standardize semantic tokens (`surface.*`, `text.*`, `border.*`, `accent.*`, `semantic.*`) in `design-system/tokens/`.
2. **App Shell V6**: Stable 3-pane capable layout preserving state across Talk, Work, and Operate.
3. **Composer V6**: Context Chips V2, Smart `+` Menu, Auto/Fast/Deep/Max intelligence tiers, Goal & Create modes.
4. **Referent-Before-Research Backend Fix**: Prevent ungrounded pronouns ("tell me more about her" in fresh sessions) from firing 24-source web crawls before identifying the referent.
5. **CurrentEventResolver Two-Stage Pipeline**: Discover actual event facts (e.g. Kathmandu Valley monsoon floods) before generating targeted news photojournalism queries.
6. **Typed Response System**: Dedicated renderers for Media Galleries, Generated Images, Coding Tasks, Artifacts, and Approvals.
7. **Production Verification & Live Deployment**: Automated Playwright acceptance, Cloud Run / preview deployment, and durable persistence verification.
