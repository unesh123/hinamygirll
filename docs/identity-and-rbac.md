# Identity, RBAC, API keys and audit

Code: `apps/api/hinaa_api/orgs/` (models, permissions, service, gate, router), `AuthContext` in
`persistence/auth.py`, migration `0018_identity`. UI: Organisation page (`/organisation`, also in the
command palette).

## Organisations and roles

- Every authenticated user gets a **personal organisation** on first request (idempotent) and is its `owner`.
  This holds in dev, Clerk and OIDC modes; `HINAA_ALLOWED_USER_IDS` still gates who may authenticate at all.
- `resolve_auth` attaches `org_id`, `role`, `permissions` (and `api_key_id` for key auth) to `AuthContext`.
  Send `X-HINAA-Org: <org id>` to act in another organisation you belong to (non-members get 403).
- Roles: `owner`, `admin`, `member`, `viewer`. An organisation always keeps at least one owner; only owners can
  grant, change or remove the owner role.

| Permission | owner | admin | member | viewer |
| --- | :-: | :-: | :-: | :-: |
| `org:manage` | ✓ | | | |
| `members:manage` | ✓ | ✓ | | |
| `apikeys:manage` | ✓ | ✓ | | |
| `audit:read` | ✓ | ✓ | | |
| `tools:execute_high_risk` | ✓ | ✓ | | |
| `tools:execute` | ✓ | ✓ | ✓ | |
| `data:write` | ✓ | ✓ | ✓ | |
| `data:read` | ✓ | ✓ | ✓ | ✓ |

`OrgGate.require_permission(*perms)` is the FastAPI dependency; denials return 403 `PERMISSION_DENIED` and are audited.
`POST /v1/tools/execute` requires `tools:execute`, plus `tools:execute_high_risk` for `IRREVERSIBLE_EXTERNAL_TOOLS`.
Requests that present no credentials at all keep the pre-existing Host-based tool policy unchanged.

## API keys

- `POST /v1/org/api-keys` returns the full key (`hk_<prefix>_<secret>`) **once**; listings show the prefix only.
- Stored as `HMAC-SHA256(pepper, salt:secret)` with a per-key salt; compared in constant time. The pepper is
  `HINAA_API_KEY_PEPPER`, or a random value generated into `.runtime/api_key_pepper` (0600). Rotating the pepper
  invalidates existing keys.
- Scopes must be a subset of the permissions the creator holds. Effective permissions are the key's scopes intersected
  with the creator's current role, so demoting or removing the creator narrows or kills the key.
- Optional expiry (`expiresInDays`); revoked, expired or unknown keys get 401. `last_used_at` is updated on use.
- Use with `Authorization: Bearer hk_...`.

## Audit log

`org_audit_log` is append-only per organisation: `row_hash = sha256(prev_hash + canonical_json(row fields))`,
genesis `0*64`. Recorded: org creation/login bootstrap, member add/role change/remove, API key create/revoke,
`tool.execute` for LOCAL_EFFECT and IRREVERSIBLE tools, and `permission.denied`. Each row has user, action, target,
outcome, request id (ops middleware), HMAC'd client IP (never raw) and timestamp. There is no update/delete API
and the ORM refuses mutation; `GET /v1/org/audit/verify` recomputes the chain and reports the first invalid sequence.
Note: verification detects edits, deletions in the middle and reordering; truncating the tail needs an external anchor of
`headHash`, which the response provides.

## Endpoints (`/v1/org`, also `/api/v1/org`)

| Method and path | Permission |
| --- | --- |
| `GET /me` | `data:read` |
| `GET /members` | `data:read` |
| `POST /members` `{userId, role}` | `members:manage` |
| `PATCH /members/{userId}` `{role}` | `members:manage` |
| `DELETE /members/{userId}` | `members:manage` |
| `GET /api-keys`, `POST /api-keys`, `DELETE /api-keys/{id}` (revoke) | `apikeys:manage` |
| `GET /audit?limit&offset&action&userId&outcome` | `audit:read` |
| `GET /audit/verify` | `audit:read` |

Schema uses SQLAlchemy Core table definitions only (portable to Postgres). Requires persistence to be enabled.
