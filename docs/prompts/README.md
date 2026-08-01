# Prompt specifications

These files define independently versioned prompt layers. They are implementation specifications, not claims of finalized production prompts. Server assembly supplies trusted policy/character settings and delimits all retrieved/user/tool/vision content as untrusted data. Every output is validated against a schema/allowlist; no prompt grants permission.

**Runtime status (Tier A):** layered assembly is implemented in `apps/api/hinaa_api/prompts/`. See [TIER-A-RUNTIME.md](TIER-A-RUNTIME.md) and [26-tier-a-conversation-brain-implementation.md](../26-tier-a-conversation-brain-implementation.md).

Promotion requires prompt-injection, boundary, multilingual, schema and regression evaluation with a version hash. Production prompt changes require review and rollback metadata. Real-provider linguistic quality remains owner-gated and unmeasured until the capped paid validation script is explicitly approved.
