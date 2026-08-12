# HINAA VSeeFace and VMC Compatibility Changelog

## Asset and runtime baseline — 2026-08-12

| Check | Result |
|---|---|
| Existing Hinaa/Hinaa Classic models | Preserved; no binary modification was made. |
| User-named VSeeFace model | `5798998195377315936 (1).vrm` was not present under `/home/ubuntu`; model-specific compatibility and visual calibration cannot be claimed. |
| VSeeFace desktop application | Not available as a runnable sandbox process; camera tracking could not be tested with a real user face. |
| HINAA VMC listener | The API starts one UDP listener at `127.0.0.1:39539` and exposes the already implemented WebSocket route at `/ws/vmc`. |
| Browser consumer | `useVSeeFace` opens a single WebSocket only when Face tracking is selected, resets face state on disconnect, and supplies blendshapes to `AvatarPresence`. |
| Hand-pose safety | `AvatarPresence` deliberately leaves VMC bone transforms out of limb control; this protects the calibrated natural hand pose from incompatible sender axes. |

## Verified local transport contract — 2026-08-12

A live local runtime probe connected to `ws://127.0.0.1:8000/ws/vmc`, sent one OSC VMC UDP packet to `127.0.0.1:39539`, and received the mapped update through the WebSocket.

| Probe input | Observed HINAA output | Result |
|---|---|---|
| `/VMC/Ext/Blendshape/Val`, `Fcl_MTH_Open`, `0.62` | `mouthOpen: 0.62` in the WebSocket payload | **VERIFIED** |

> This validates the supported local data path: VSeeFace-compatible VMC sender → UDP listener → blendshape normalization → browser WebSocket → HINAA facial-expression input. It does not assert that a missing, untested VRM will render correctly in VSeeFace.

## Support boundary

| Capability | State | Evidence or limitation |
|---|---|---|
| Mouth open, smile, blink, brows, cheek puff | **SUPPORTED** | `_BLEND_MAP` accepts VRM and ARKit-style names and forwards normalized values. |
| Head/bone quaternions | **TRANSPORTED, NOT APPLIED TO LIMBS** | The bridge forwards them, but the avatar intentionally retains its rig-safe hands and body pose. |
| Avatar speech lip-sync | **SUPPORTED IN HINAA** | HINAA's speech visemes remain the trusted mouth source outside optional external tracking. |
| Specific user model `5798998195377315936 (1).vrm` | **BLOCKED** | Asset absent; no load, calibration, or visual test was possible. |
| Full VSeeFace camera-tracking session | **BLOCKED** | No VSeeFace process/camera sender is available in this sandbox. |

## Change records

| File | Reason | Affected subsystem | Regression risk | Tests | Runtime evidence |
|---|---|---|---|---|---|
| `apps/api/hinaa_api/vmc_bridge.py` | Inspected only; confirmed a singleton UDP listener, OSC parser, blendshape map, and WebSocket broadcast path already exist. | Local VMC transport | None; no source change | Live local UDP-to-WebSocket probe | **PASS**: `Fcl_MTH_Open=0.62` reached `/ws/vmc` as `mouthOpen=0.62`. |
| `apps/web/src/features/audio/useVSeeFace.ts` | Inspected only; confirmed explicit connect/disconnect and reset behavior. | Browser tracking lifecycle | None; no source change | Source inspection and live API transport probe | Tracking data contract verified; real VSeeFace sender remains unavailable. |
| `apps/web/src/components/ui/AvatarPresence.tsx` | Inspected only; confirmed external face tracking cannot twist HINAA's calibrated hands. | Avatar pose safety | None; no source change | Source inspection | Limbs intentionally remain on the rig-safe pose. |
| `docs/HINAA_VMC_CHANGELOG.md` | Replaced pending status with validated implementation and truthful limitations. | Evidence ledger | Documentation only | Review | Model-specific claim remains explicitly blocked. |
