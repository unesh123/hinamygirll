# HINAA Windows VRM Asset Inventory

## Evidence boundary

This document defines HINAA’s **runtime inventory contract**. It is intentionally not a claim that a named model is absent from the user’s Windows computer. The current session has no connected Windows desktop filesystem, so the table below can only be populated by running HINAA’s local `/v1/avatar-assets` inventory in that actual runtime.

| Inventory source | Scan policy | Path exposed to React | Status in current sandbox |
|---|---|---|---|
| `apps/web/public/models/` | Approved HINAA application root only | Browser-safe `/models/<file>` URL when appropriate | **BLOCKED_IN_SANDBOX** for Windows evidence |
| `apps/web/src/assets/` | Approved HINAA application root only | Never exposes a filesystem path | **BLOCKED_IN_SANDBOX** for Windows evidence |
| `assets/`, `models/`, `public/` | Approved HINAA application roots only | Browser URL only when specifically served | **BLOCKED_IN_SANDBOX** for Windows evidence |
| `~/.hinaa/workspace/avatars/` | HINAA-managed copies created through explicit file-picker import | Opaque asset ID plus `/api/v1/avatar-assets/<id>/file` | **BLOCKED_IN_SANDBOX** for Windows evidence |
| Browser file picker | One file chosen explicitly by the user | No original path is sent to React or persisted in frontend state | **BLOCKED_IN_SANDBOX** until used in Windows runtime |

## Runtime record schema

Each endpoint inventory record includes an opaque ID, display name, source, browser-safe URL if available, parsed VRM version, actual file size, humanoid bone list, expression inventory, spring-bone presence, and license metadata summary. HINAA derives the VRM version from glTF extension metadata, never from the filename.

| VRM result | VSeeFace state | Browser state | Rule |
|---|---|---|---|
| `0.x` with parseable humanoid rig | **VSeeFace compatible candidate** | Browser candidate | A real VSeeFace load remains necessary before final compatibility is verified. |
| `1.0` | **VSeeFace incompatible** | Browser candidate | It is not renamed, rewritten, or represented as a 0.x model. |
| Unknown/non-VRM | Unknown | Unsupported or metadata-only | Not importable for the browser renderer. |

> The user-selected original file is never overwritten. HINAA copies only a parse-validated asset into a new opaque-ID managed directory after explicit import. Delete removes the managed copy only after confirmation; it never touches the original selected file.

## Current Windows asset result

**BLOCKED_IN_SANDBOX.** Connect the real Windows HINAA workspace, open **Avatar Lab**, and select **Refresh inventory**. This generates the truthful runtime model list without recursively scanning unrelated private directories.

## Repository-local parsed inventory — 2026-08-13

The following inventory was returned by the new local API running against the checked-out HINAA repository. It demonstrates parser behavior and provides browser-candidate metadata for the bundled assets. It does **not** establish that these are the user’s requested Windows VSeeFace assets or that any has successfully loaded in VSeeFace.

| Asset | Parsed VRM version | VSeeFace status | License metadata summary | Evidence state |
|---|---|---|---|---|
| `AvatarSample_E` | 1.0 | Incompatible | VRM 1.0 licence URL; personal non-commercial use | **INTEGRATION_TESTED** parser only; not offered in HINAA selector. |
| `hinaa` | 0.x | Compatible candidate | `licenseName: Other`; author `rurune` | **INTEGRATION_TESTED** parser only; real VSeeFace load unverified. |
| `model_5447` (Hinaa Classic) | 1.0 | Incompatible | VRM 1.0 licence URL; corporate commercial usage | **INTEGRATION_TESTED** parser only; browser candidate only. |
| `model_6164` (Hinaa) | 0.x | Compatible candidate | `licenseName: Other`; author `Peach` | **INTEGRATION_TESTED** parser only; real VSeeFace load unverified. |

The prior rejected B/C models are still not included in the current HINAA selector. A runtime-managed import is never auto-selected, never changes the original file, and must be explicitly chosen in Avatar Lab after import.
