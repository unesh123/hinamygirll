# HINAA Classic → Sakura Migration Plan

## Status: Phase A — In Progress

## Canonical Interface

**Sakura OS is the canonical interface.** Classic mode is deprecated and will be removed
after full migration verification.

## Component Mapping

| Classic Component | Sakura Component | Migration Status | Notes |
|-------------------|------------------|------------------|-------|
| NavRail | NavigationRail | ✅ Created | Needs tooltip, keyboard nav |
| PremiumComposer | ChatComposer | ✅ Created | Needs power-up integration |
| TranscriptView | ChatMessage | ✅ Created | Needs streaming cursor |
| FullScreenAura | TalkMode | ✅ Created | Needs VRM/Orb verified |
| ActionChips | ChatComposer chips | ✅ Created | Integrated into composer |
| MemoryPanel | — | 🔲 Shared overlay | Works from both modes |
| SettingsDialog | — | 🔲 Shared overlay | Works from both modes |
| ContextWorkspace | — | 🔲 Shared overlay | Works from both modes |
| AvatarPresence | AvatarPresence (shared) | 🔲 Shared lazy | 1.1 MB — needs splitting |
| Tool approval (inline) | ToolApprovalCard | ✅ Created | Needs real tool testing |
| VmcControlPanel | — | ❌ Sakura missing | Must add to TalkMode |
| AvatarLab | — | 🔲 Shared overlay | Works from both modes |
| SidebarPanel | — | ❌ Sakura missing | Must integrate or replace |
| ParticleOrbitEffect | — | ✅ Removed | Decorative, not needed |
| FullScreenAura | — | ✅ Removed | Replaced by TalkMode |

## Exit Criteria for Removing Classic

1. ✅ Every classic feature accessible from Sakura shell
2. 🔲 Talk mode: VRM import, VMC connection, VSeeFace controls work
3. 🔲 Talk mode: Voice session starts, interrupts, recovers
4. 🔲 Work mode: Chat sends, streams, stops correctly
5. 🔲 Work mode: Tool approvals display with real tool calls
6. 🔲 Work mode: Memory editing and deletion works
7. 🔲 Work mode: Project switching during conversation works
8. 🔲 Operate mode: Only shows real, verified capabilities
9. 🔲 Mobile: Navigation works with keyboard open
10. 🔲 Mobile: Controls don't overlap captions/avatar
11. 🔲 Mode switching while HINAA is speaking doesn't crash
12. 🔲 Mode switching while tool is executing doesn't crash
13. 🔲 Page refresh preserves selected mode
14. 🔲 Browser back/forward navigation works
15. 🔲 No duplicate navigation systems in final bundle

## Blocked Items

- VSeeFace/VMC controls need TalkMode integration
- SidebarPanel equivalent needed for Sakura
- Full conversation history browsing needs Sakura path

## Rollback

If Sakura mode breaks critical functionality:
1. Set `sakuraMode` default to `false` in App.tsx
2. Classic mode is fully preserved behind the toggle
3. No Classic components are deleted until exit criteria pass
