# 31 — Privacy and data controls

## User-visible controls (API)

- Memory on/off with consent audit events
- List explicit memories with provenance fields
- Forget individual memory
- Clear conversation
- Export data (no secrets)
- Delete all account data (soft-delete + revoke memories)

## Data flow disclosure (status payload)

- Gemini: conversation text when real mode enabled
- Azure Speech: audio stream when real mode enabled
- Raw microphone audio: not stored by default
- Summaries: marked generated, not literal transcripts

## Auth

- Local/dev: `HINAA_AUTH_MODE=dev` + `X-HINAA-Dev-User`
- Production target: OIDC (`HINAA_OIDC_ISSUER`) — validation not fully enabled offline

## Retention policy (documented defaults)

- Deleted content purge target ≤30 days (operational enforcement depends on deployment jobs)
- Audit/consent append-only rows retained for pilot review
- No dark patterns in API (explicit enable required before remember when disabled)

## Frontend

Privacy dashboard UI should call these endpoints with accessible confirmations. Core API contract is ready for a privacy panel; full polished dashboard is incremental.
