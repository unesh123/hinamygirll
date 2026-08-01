# ADR-013: Dev auth and OIDC scaffold

## Status

Accepted for local development.

## Decision

- `HINAA_AUTH_MODE=dev` trusts `X-HINAA-Dev-User` for privacy endpoints.
- `oidc` mode requires bearer tokens; full JWT validation is deployment-gated.
- Optional scaffold tokens (`scaffold:<subject>`) only when `HINAA_ALLOW_OIDC_SCAFFOLD_TOKENS=true` for automated tests.

## Consequences

- Production must set `auth_mode=oidc` with a real issuer and disable scaffold tokens.
- WebSocket private persistence authorization remains a follow-up hardening item.
