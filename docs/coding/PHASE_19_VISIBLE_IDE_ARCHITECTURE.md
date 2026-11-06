# HINAA OS — Phase 19 Visible IDE Architecture

## Architectural Thesis
AI coding agents too often reduce the software engineering experience to simulated progress bars, text token streams, or unverified hallucinations. Phase 19 dismantles this by introducing **The Visible AI Developer**: a fully inspectable, multi-panel developer workbench where every action is backed by:
1. Genuine disk writes into isolated workspaces (`.runtime/coding/workspaces/{workspace_id}`)
2. Strictly typed, monotonic SSE event streams with cursor-based reconnection (`Last-Event-ID` & `after_seq`)
3. Isolated browser iframe sandboxing with strict Content-Security-Policy headers and hot-reloading bridges
4. Objective Design Critic evaluations (scoring 0–100 across 6 axes)
5. Tamper-evident cryptographic evidence manifests with SHA256 checksums and one-click ZIP exports

---

## Component Topology

```
+-----------------------------------------------------------------------------------------+
|                                HINAA DEVELOPER STUDIO                                   |
|                               (apps/web/src/components/coding)                          |
+-----------------------------------------------------------------------------------------+
|  Top Bar: Mission Selector, Run Mission, Run Preview, Reset, Export ZIP, Live Status   |
+------------------------+------------------------------------+---------------------------+
|   PROJECT EXPLORER     |           SOURCE EDITOR            |     LIVE RENDERED SITE    |
|  - Real file tree      |  - Tabbed file editing             |  - Responsive iframe      |
|  - File size metrics   |  - Monospace syntax typography     |  - Desktop (1440px)       |
|  - Change dot alerts   |  - Line counters                   |  - Tablet (768px)         |
|  - Critic score badge  |  - Ctrl+Enter / Ctrl+S shortcuts   |  - Mobile (390px)         |
+------------------------+------------------------------------+---------------------------+
|                          DRAWER: ACTIVITY, LOGS & TELEMETRY                             |
|  [Actual changes]   [Terminal & Build]   [Design Critic]   [Event Stream]   [Evidence]  |
+-----------------------------------------------------------------------------------------+
                                         ▲  ▼
                     REST & Server-Sent Events (SSE) `/api/coding`
                                         ▲  ▼
+-----------------------------------------------------------------------------------------+
|                                 FASTAPI CODING BACKEND                                  |
|                             (apps/api/hinaa_api/coding)                                 |
+-----------------------------------------------------------------------------------------+
|  DeveloperEventStore   | ProjectEngine        | PreviewRuntime      | DesignCritic      |
|  - SQLite WAL (seq)    | - Workspace Manager  | - Sandboxed iframe  | - 6 Rubric axes   |
|  - SSE pub/sub queue   | - Diff Engine        | - CSP headers       | - WCAG checks     |
|  - Secret redaction    | - Build execution    | - Hot-reload bridge | - Nepali fidelity |
+-----------------------------------------------------------------------------------------+
```

---

## 1. Event Stream Monotonicity & WAL Resumption
Every interaction in the studio is captured by `DeveloperEventStore`.
- Events are assigned a strictly monotonic integer `seq` per task.
- Written to `.runtime/coding/developer_events.db` in SQLite Write-Ahead Logging (WAL) mode.
- Clients can reconnect at any time using the HTTP `Last-Event-ID` header or `?after_seq=X` query parameter.
- The server first replays all events with `seq > after_seq` before streaming live events from the in-memory queue.
- Sensitive credentials (tokens, API keys, passwords) are automatically redacted before disk write and client broadcast.

## 2. Sandboxed Preview Runtime & Security Containment
Live websites are rendered inside an `<iframe>` served from `/api/coding/preview/{preview_id}/{path}`:
- **Strict Content Security Policy**:
  - `default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https://fonts.googleapis.com https://fonts.gstatic.com;`
  - `frame-ancestors 'self' http://localhost:5173 http://127.0.0.1:8000;`
- **MIME Type Accuracy**: Explicit mapping for `.html`, `.css`, `.js`, `.mjs`, `.svg`, `.json`.
- **Directory Traversal Protection**: Any path containing `..` or leading slashes outside the workspace root is rejected with a `404 Not Found`.
- **Hot-Reload & Error Bridge**: Injects a lightweight script into HTML responses to capture runtime errors and postMessage them to the parent workbench.

## 3. Autonomous Project Engine
`AutonomousProjectEngine` acts as the orchestrator:
- Manages workspaces under `.runtime/coding/workspaces/{workspace_id}`.
- Executes flagship missions and custom projects.
- Tracks unified diffs between file revisions using Python's `difflib`.
- Runs real build validation commands and logs exit codes and stdout.
- Produces cryptographic evidence bundles with SHA256 hashes of every file.
