# HINAA OS — Phase 21 UI & Trace Evidence

## 1. Developer Studio Live Wiring
The Developer Studio interface is directly connected to the active FastAPI backend (`http://127.0.0.1:8000`) and Vite dev server (`http://localhost:5173`).

### 1.1 Verified UI Capabilities
1. **Interactive Flagship Missions:** Missions `M1` through `M6` can be selected from the mission switcher dropdown.
2. **Real-Time Task Execution:** Clicking **⚡ Run Mission** dispatches a live `POST /api/coding/missions/{id}/run` call.
3. **SSE Event Stream:** Subscribes to `/api/coding/tasks/{taskId}/events` displaying streaming workspace operations:
   - `file.opened`
   - `file.saved`
   - `file.patch.applied`
   - `command.started` / `command.stdout` / `command.exited`
   - `preview.ready`
   - `plan.updated`
   - `artifact.verified`
   - `task.completed`
4. **Sandboxed Live Preview:** Rendered inside isolated iframe with strict CSP (`frame-ancestors 'self'`) and sandbox parameters.
5. **Multi-Viewport Switching:** Instant responsive preview testing across Desktop (1440px), Tablet (768px), and Mobile (390px).
6. **Task Control Actions:** Pause, resume, and midway requirement updates without leaving the workbench.
7. **Export Capability:** One-click ZIP download via `/api/coding/tasks/{taskId}/export`.

---

## 2. Event Store Trace Evidence Sample

```json
[
  {
    "seq": 1,
    "kind": "task.started",
    "actor_role": "Hinaa-DevAgent",
    "payload": {
      "title": "Kathmandu Flight Charter & Helicopter Rescue Dispatcher",
      "mission_code": "M1",
      "phase": "Phase 21"
    }
  },
  {
    "seq": 2,
    "kind": "file.saved",
    "file_path": "schema.sql",
    "new_sha256": "4b971a82e9d2cf1f845014f3b791dc0c611ec5a4ffbc6e5e8e815e34891bca7a"
  },
  {
    "seq": 3,
    "kind": "preview.ready",
    "payload": {
      "preview_url": "/api/coding/preview/prev-910283/index.html",
      "viewports": ["desktop_1440", "tablet_768", "mobile_390"]
    }
  },
  {
    "seq": 4,
    "kind": "task.completed",
    "payload": {
      "task_id": "task-8f921a8c",
      "score": 96
    }
  }
]
```
