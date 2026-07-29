# Security, privacy and threat model

## Purpose

Apply STRIDE and privacy-by-design to microphones, cameras, prompts, providers, assets, memory, and future tools.

## Decision

### Trust boundaries

Browser/device, public edge, FastAPI, database, secret store, object storage and each external provider are separate trust zones. All client input, model output, retrieved content, camera observations, tool output and uploaded assets are untrusted. Authentication does not imply authorization.

### STRIDE register

| Threat | Examples | Required controls |
|---|---|---|
| Spoofing | stolen session, socket hijack, fake provider callback | OIDC/OAuth code+PKCE, Secure HttpOnly SameSite cookies, CSRF token for mutation, Origin check, short socket ticket, TLS, re-auth sensitive changes |
| Tampering | replayed chunks, edited tool plan, poisoned memory | event IDs/sequences, idempotency, schema/allowlist validation, ownership checks, append-only audit, hashes/signatures for assets |
| Repudiation | denied key/memory/tool change | redacted append-only consent/audit with actor, result, policy version and trace |
| Information disclosure | key/log leakage, cross-user memory, camera/audio misuse | server secrets/Key Vault, envelope encryption, RLS, redaction, just-in-time permissions, no continuous capture, signed short asset URLs, private defaults |
| Denial of service | oversized audio/VRM, socket flood, provider cost abuse | byte/duration/concurrency limits, rate/quota limits, timeouts/circuits, decompression limits, budget kill switch |
| Elevation of privilege | IDOR, SSRF, prompt-driven tool execution | per-object authorization, fixed provider base URLs, egress allowlist, no arbitrary URLs/files/bones, deterministic tool validator, least-privilege service identities |

### Specific controls

- Frontend contains no permanent provider key; `VITE_*` is public configuration only.
- CSP default-src self; narrowly allow media/connect origins; frame-ancestors none; HSTS, nosniff, Referrer-Policy, Permissions-Policy; output encoded and Markdown sanitized without raw HTML.
- REST/body/audio/asset type and size limits; parameterized ORM; canonical MIME sniffing; archive bombs rejected.
- WebSocket validates Origin, session, CSRF-bound one-time ticket, sequence, message schema and liveness; ticket <=60 s, connection idle timeout, no tokens in URL logs.
- SSRF prevention uses adapter-owned URLs, DNS/IP range rejection, redirect off, egress firewall and metadata endpoint block.
- VRM/GLTF: quarantine, checksum, vertex/texture/accessor limits, external URI disabled, isolated object origin, no scripts/extensions outside allowlist.
- Prompt injection: immutable policy separated from quoted untrusted blocks; tool calls off in MVP; retrieved content cannot change policies; structured output schema; adversarial regression corpus.
- Camera: permission immediately before one request, persistent indicator, one-tap stop, low-resolution still, explicit purpose, no identity/emotion diagnosis, deletion control.
- Supply chain: lockfiles, minimal dependencies, provenance/SBOM, Dependabot-equivalent scanning, secret scanning, signed CI artifacts, licence review.

### Incident response

Detect/triage → disable affected provider/tool/credential via kill switch → revoke/rotate keys and sessions → preserve redacted evidence → assess users/data → notify according to applicable obligations → patch/test/deploy → postmortem. Maintain owner/contact and tabletop before pilot. Never promise a legal notification period until jurisdiction and controller obligations are reviewed.

### Privacy operations

Consent is purpose/version specific and revocable. Export produces user-readable JSON plus media manifest. Deletion follows active/backup schedules in the database design. Analytics are opt-in for research; avoid advertising identifiers. Document provider processors, region, retention and training terms before enabling real user data.

## Alternatives considered

LocalStorage bearer tokens and client provider keys are simpler but exposed to XSS/decompilation. Automatic camera/memory improves convenience but violates user agency.

## Reasoning

The highest-impact failures are credential disclosure, cross-user memory, covert sensors and prompt-to-action escalation; the architecture prevents them at multiple boundaries.

## Risks

No blueprint proves compliance. Nepal and deployment-region privacy/legal requirements need supervisor/legal review before public pilot. Third-party terms change.

## Acceptance criteria

- Threat cases have automated abuse tests where feasible.
- Secret scan and dependency scan gate releases.
- Two-user authorization suite covers every private endpoint/table.
- Camera/mic/memory consent and revocation are demonstrable.
- Incident tabletop completes before external pilot.

