# 40 — Post-MVP capability plan

Do **not** implement these in the core completion pass without separate authorization.

| Capability | Value | Permission | Data | Confirmation | MVP exclusion |
|---|---|---|---|---|---|
| Web search | Fresh facts | Explicit enable | Query + snippets ephemeral | Per-query or session | Tool policy disabled |
| Calendar | Schedule help | OAuth calendar scope | Event metadata | Before write | Irreversible writes risk |
| Email draft | Productivity | OAuth mail scope | Draft content | Before send | Send is irreversible |
| Device control | Convenience | OS permission + deny-by-default | Device commands | Always | Autonomous control forbidden in MVP |
| Camera/vision | Scene help | Per-session camera | Frames ephemeral | Before capture | Privacy/surveillance risk |
| Image generation | Creative | Explicit enable | Prompts | Per request | Cost + safety filters |
| Multi-provider routing | Resilience | Admin config | Telemetry only | N/A | Complexity |
| Custom licensed voice | Identity | Written talent agreement | Voice dataset | Legal intake | Licence gate |
| Multi-device sync | Continuity | Account auth | Encrypted sync | Device link | Needs auth+DB |
| Native wrapper | Store distribution | Store accounts | Same as PWA | N/A | PWA-first MVP |

All future tools must use static allowlists, typed args, least privilege, audit logs, and no model-invented tool names.
