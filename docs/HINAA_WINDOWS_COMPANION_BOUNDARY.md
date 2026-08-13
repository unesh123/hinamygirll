# HINAA Trusted Windows Companion Boundary

**Status:** Architecture contract; no Windows companion process has been shipped or verified in this repository.

HINAA’s browser application and local FastAPI service may organize projects, research, conversation, imported files, and agent plans. They do **not** have authority to inspect or control the user’s Windows desktop, camera, microphone, VSeeFace installation, browser session, messaging applications, music player, IDE, or operating-system settings. Those capabilities require a separately installed, user-visible Windows companion that is paired locally and has narrowly scoped permissions.

> **A connected socket or a bound UDP port is not evidence of live tracking or device control.** HINAA can label a capability “live” only after it receives fresh, valid packets or an action receipt from the trusted local companion during the active session.

## Design goals

The companion must remain local-first, least-privileged, understandable, and revocable. It must make every consequential action visible before it occurs, keep an audit record in the user’s local HINAA workspace, and never attempt to bypass a website’s access controls, authentication, captchas, application permissions, or operating-system protections. Microsoft UI Automation provides programmatic access to many Windows UI elements, but it is not a license to act outside the user’s approved scope or across different Windows users.[1]

| Requirement | Contract |
|---|---|
| **Transport** | Loopback-only HTTPS or named-pipe control plane. A remote LAN or Internet binding is disabled by default and requires a separately visible configuration change. |
| **Pairing** | Each browser/API session displays a short-lived pairing code. The companion confirms the code locally, creates a device-bound key, and exposes only the user-selected capabilities. |
| **Action integrity** | Every proposed action includes a stable `actionId`, capability, target, human-readable preview, expiry, and risk level. The companion rejects altered, stale, duplicate, or unapproved actions. |
| **Approval** | HINAA asks for approval after showing the exact effect. A completion receipt is recorded only after the local companion reports the result. Browser/API approval tokens are non-resumable; a new request is required after reload or expiry. |
| **Visibility** | Screen/camera/microphone use shows a persistent live indicator, source name, timestamp, and immediate stop control. The companion does not silently capture in the background. |
| **Audit and revocation** | A local audit record stores request, preview, approval choice, action receipt, and failure detail. The user can revoke a capability or unpair the companion at any time. |

## Capability contract

The following table distinguishes what HINAA can do today from what a future Windows companion may do after installation, pairing, approval, and real-runtime evidence.

| Capability | HINAA current local capability | Windows companion scope | Required preview and approval | Runtime acceptance evidence |
|---|---|---|---|---|
| **Desktop screen reading** | None. HINAA cannot see the Windows desktop. | Capture only a user-selected window or one explicitly requested frame; send the frame to the local API only for the requested analysis. | Show target window name and whether capture is one-time or continuous. Continuous sharing must have a persistent indicator and Stop control. | Companion status, target title, capture timestamp, user-visible indicator, and the analyzed frame/artifact. |
| **Camera / face data** | Browser microphone/live UI only; no desktop camera access. | Camera frames remain inside VSeeFace or the chosen tracker. HINAA receives only the opted-in VMC transform/expression stream, never raw frames by default. | User starts tracking in VSeeFace and explicitly enables the paired receiver. | Fresh VMC heartbeat, monotonic timestamps, dropped-packet count, and observed head/blink/expression response. |
| **VSeeFace / VMC avatar motion** | Existing browser viewer consumes the present VMC bridge only; it must show stale/offline when packets stop. | Receive VMC OSC/UDP on an explicit local endpoint and translate only valid, fresh samples. The companion must not modify VRM binaries or announce tracking merely because a socket opened. | Enable receiver, target host/port, selected VRM profile, and calibration are all visible. | Valid `/VMC/Ext/T` heartbeat and current transforms/blend values; status becomes stale after a short timeout. The VMC specification uses OSC over UDP/IP and permits senders/receivers to ignore unsupported or malformed messages.[2] |
| **Voice control** | Browser live voice can be started by the user and shows provider errors. | Optional local endpoint detection/noise processing only while a live session is armed. No always-on wake word by default. | Start/stop listening, selected input, speech-to-text provider, and any external audio transfer. | Input-meter activity, partial transcript, recognized command, action preview, and a single audio-playback receipt. |
| **Browser navigation** | Existing browser agent can propose navigation and requires approval for consequential steps. | Open or focus a single user-chosen browser tab through an allowlisted browser adapter. It cannot evade logins, paywalls, access control, or captchas. | Full URL, target browser profile, and whether a new tab will open. Submissions, downloads, uploads, and purchases each need a separate preview. | Exactly one tab receipt with URL and title; no duplicate-window receipt. |
| **WhatsApp / email / social messages** | HINAA can draft text only. | Compose into a selected client after an approved recipient and text preview. It must not read all conversations, auto-reply, or send silently. | Recipient, account/app, exact message body, attachments, and send action. | Explicit send receipt from the companion; a failed/unknown outcome remains unconfirmed. |
| **Spotify / media** | HINAA can suggest search terms or links. | Search/open/play only in a user-selected local media/browser adapter. Playback state must be reported honestly. | Service, query, selected result, account context if applicable, and play/pause/queue action. | Media app focus or browser-tab receipt plus reported playback state. |
| **VS Code / local files** | HINAA stores private project artifacts and may create an approved local task plan. | Inspect a user-selected workspace. File writes, command execution, extension changes, and git operations are separate actions. | Workspace root, exact files, diff/patch, terminal command, and expected effects. | File/diff receipt, command stdout/stderr, and test outcome saved as a project artifact. |
| **System settings / power** | None. | Read permitted system facts; execute limited, explicit controls such as volume or opening Settings. Shutdown, restart, network, security, installation, and privilege changes are high-risk and require repeated confirmation. | Exact setting or command, before/after state, and reversibility. | Local receipt with returned state; no claim of success without one. |
| **Scheduling** | HINAA can keep an in-app task plan. | Register a named, visible Windows Task Scheduler job after explicit approval. No short-interval polling. | Trigger, program/arguments, working directory, credentials/privilege level, battery conditions, and cancel path. | Task identifier plus read-back of its registered definition. Microsoft recommends Task Scheduler 2.0 for new development and warns against short-interval polling on battery-powered devices.[3] |

## Minimal protocol

A future companion should expose a versioned, loopback-only protocol. Its capability list should be declarative, so HINAA can present unavailable features truthfully instead of manufacturing results.

```json
{
  "protocol": "hinaa-windows-companion/v1",
  "deviceId": "paired-local-device",
  "capabilities": {
    "screenCapture": { "enabled": false, "continuousAllowed": false },
    "vmcReceiver": { "enabled": true, "endpoint": "127.0.0.1:39540" },
    "browser": { "enabled": false, "allowedProfiles": [] },
    "messaging": { "enabled": false },
    "ide": { "enabled": false, "roots": [] }
  }
}
```

The API requests an action only in the following shape. The local companion must render or notify the user of the `preview` before accepting an approval response. It must never infer “yes” from model text, a stale browser click, a previous approval, or a voice utterance with ambiguous intent.

```json
{
  "actionId": "uuid",
  "capability": "messaging.composeAndSend",
  "risk": "external-send",
  "preview": {
    "application": "WhatsApp Desktop",
    "recipient": "Asha",
    "body": "I will be 10 minutes late.",
    "attachments": []
  },
  "expiresAt": "2026-08-14T12:00:00Z"
}
```

A response receipt is a fact, not a prediction:

```json
{
  "actionId": "uuid",
  "state": "completed",
  "completedAt": "2026-08-14T11:58:18Z",
  "evidence": { "windowTitle": "WhatsApp", "result": "message sent" }
}
```

The supported states are `proposed`, `approved`, `declined`, `executing`, `completed`, `failed`, `expired`, and `unknown`. If the adapter cannot determine whether an external operation succeeded, it must return `unknown`; HINAA must state that clearly.

## VSeeFace and avatar truthfulness contract

HINAA’s avatar renderer should maintain two distinct motion layers. The **idle companion layer** supplies safe breathing, gaze, subtle emotion, and lip-sync while no external tracking is active. The **external VMC layer** replaces only measurements supported by fresh packets and fades out if they become stale. It must never leave a last received open-mouth, T-pose, or raised-arm transform frozen after tracking stops.

The VMC protocol defines blend-shape and bone messages separately and explicitly notes VRM 0.x/VRM 1.0 expression differences; its blend-shape names are case-sensitive in non-permissive implementations.[2] Therefore, the Windows acceptance pass must test each imported avatar’s humanoid bone mapping, expression aliases, neutral calibration, stale-sample reset, face-forward portrait framing, and mouth close after audio ends. HINAA must preserve original VRM files and store any user adjustments as separate per-avatar profile data.

| Avatar state | Required UI copy | Required technical condition |
|---|---|---|
| **Idle** | “Companion animation” | No fresh external VMC sample; local idle pose drives the model. |
| **Awaiting tracking** | “VSeeFace ready — waiting for motion” | Receiver may be configured, but no valid packet has arrived recently. |
| **Tracking live** | “VSeeFace live — receiving motion” | Valid heartbeat/sample within the stated timeout and an observed transform or expression update. |
| **Stale / disconnected** | “Tracking paused — returning to companion pose” | Timeout exceeded, invalid sample, or transport failure. Facial/mouth values decay to neutral. |
| **Calibration required** | “Calibrate neutral in VSeeFace” | Packets exist but baseline is not accepted for this profile/session. |

## Explicitly out of scope

HINAA must not add hidden surveillance, silent background screen/camera recording, credential harvesting, bypassed logins, captcha defeat, paywall/access-control circumvention, mass messaging, auto-sending communications, invisible browser manipulation, unrestricted shell execution, automatic program installation, privilege escalation, or autonomous device takeover. “Uncensored” is not a valid reason to remove these boundaries or applicable safety protections.

## Windows acceptance checklist

A future Windows companion can be marked **verified** only after a user performs each test on the actual Windows computer:

1. Install and pair the companion with an on-screen code, then inspect the enabled capability list.
2. Request one screen capture and confirm the target title, persistent capture indicator, saved local artifact, and stop control.
3. Start VSeeFace, select an imported VRM without altering its binary, enable VMC, and observe fresh packet timestamps. Verify neutral pose, blink, gaze, head movement, expression, lip-sync, stale reset, and face-and-shoulders portrait framing.
4. Request a browser navigation and confirm exactly one tab is opened. Attempt a submission and confirm that it is blocked until a distinct preview approval occurs.
5. Draft a WhatsApp message and confirm no send happens before the recipient/body preview is approved. Validate completed, declined, and unknown receipts.
6. Open a VS Code workspace; verify that a proposed patch and terminal command show their full scope before approval and that output is retained as an artifact.
7. Create a scheduled task only after showing its trigger and command, then read its registration back and remove it through the companion.
8. Revoke the companion pairing and confirm all protected actions return `unavailable` without fallback execution.

## References

[1]: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview "Microsoft UI Automation overview"
[2]: https://protocol.vmc.info/english.html "Virtual Motion Capture Protocol specification"
[3]: https://learn.microsoft.com/en-us/windows/win32/taskschd/about-the-task-scheduler "Microsoft Task Scheduler overview"
