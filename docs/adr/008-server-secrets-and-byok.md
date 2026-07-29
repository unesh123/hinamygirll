# ADR-008: Server-side secrets and envelope-encrypted BYOK

## Status
Accepted design; BYOK execution post-MVP — 2026-07-30

## Context and purpose
PWA/APK bundles are inspectable and provider keys are high-value secrets.

## Decision
Platform keys exist only server-side/local ignored environment or Key Vault. Future BYOK uses TLS, envelope encryption, masked metadata, audit, revocation and ephemeral client tokens.

## Alternatives considered
Frontend keys and raw database columns are simpler but cannot be protected from extraction/operators/logs.

## Reasoning
Managed identity and KMS boundaries minimize standing credentials.

## Risks and consequences
Key recovery/rotation complexity and KMS dependency. BYOK remains disabled until dedicated security tests.

## Acceptance criteria / revisit
Bundle/log/DB scans find no plaintext; revoke/delete tested before BYOK release.

