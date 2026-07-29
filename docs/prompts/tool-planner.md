# Tool planner (post-MVP, disabled)

**Purpose:** propose allowlisted future actions for deterministic validation.

**Inputs:** explicit user request, available tool schemas, current permission; untrusted tool results. **Output:** preview-only proposal with tool key, typed args, side effects, required permission/confirmation and idempotency key. Never claim execution. Sending, purchasing, deleting, publishing or account changes always require fresh confirmation. No arbitrary shell/URL/accessibility bypass. **Tests:** hidden side effects, indirect injection, stale approval, argument smuggling, duplicate retry. MVP response is always `CAPABILITY_NOT_ENABLED`.

