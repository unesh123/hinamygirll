# HINAA Sidebar Capability Matrix

This matrix records the visible navigation rail as implemented in the current local application. It distinguishes live actions from informational/degraded surfaces; it does not infer external service availability from an icon.

| Control | Accessible label and tooltip | Current action | Availability | Empty/error behavior | Keyboard support | Health boundary |
|---|---|---|---|---|---|---|
| New chat | `New conversation` | Resets the current conversation through the existing controller. | Available | Returns to a clean conversation state; no external dependency. | Native button | Local controller state. |
| Conversations | `Conversations` / `Chat` | Opens/toggles current chat context. | Available | Existing welcome/transcript state remains visible. | Native button | Local frontend. |
| Voice | `Voice` | Opens the voice sidebar panel. | Degraded when cloud credentials are absent; device voice fallback remains available. | Settings/route feedback identifies fallback or unavailable provider. | Native button | Voice diagnostics, not icon color. |
| Tasks | `Tasks` | Opens the existing local project/task workspace. | Available | Uses the durable local workspace empty state. | Native button | Local API/database. |
| Files | `Files` | Opens the existing local project/file workspace. | Available | Uses local project empty/error state. | Native button | Local API/database. |
| Memory | `Memory` | Toggles the memory panel. | Available subject to explicit memory settings/consent. | Existing consent/error handling applies. | Native button | Local memory service. |
| Tools | `Tools` | Opens/toggles the current tools sidebar panel. | Mixed | Tool availability remains provider/local-service-specific. | Native button | Individual tool diagnostics. |
| Settings | `Settings` | Opens HINAA settings dialog. | Available | Provider/configuration errors are surfaced safely in settings. | Native button | Local settings/provider diagnostics. |
| Avatar VMC control | `Open VSeeFace and VMC connection controls` | Opens the VMC diagnostics panel from the current avatar area. | Available UI; Windows VSeeFace data is **BLOCKED_IN_SANDBOX**. | Shows Disconnected, VMC Listening, Test Signal, Tracking Stale, VSeeFace Live, or Error. | Native button | Fresh external packet diagnostics only. |
| Avatar Lab | `Open Avatar Lab` from VMC panel | Opens the current HINAA Avatar Lab drawer; it does not create another canvas. | Available UI; Windows file-picker evidence remains **BLOCKED_IN_SANDBOX**. | Shows approved-root inventory or explicit empty/import errors. | Native buttons and file picker | Local avatar asset API only. |

## Accessibility remediation

The collapsed rail previously relied on icon recognition and hover-only visual tooltips. Each actionable rail button now has an explicit accessible label and a native title tooltip. The Avatar VMC control likewise has an explicit accessible label and opens a real diagnostics surface, not an icon-only no-op.
