"""Role -> permission map. Roles are ordered owner > admin > member > viewer."""

from __future__ import annotations

ROLES: tuple[str, ...] = ("owner", "admin", "member", "viewer")

ORG_MANAGE = "org:manage"
MEMBERS_MANAGE = "members:manage"
APIKEYS_MANAGE = "apikeys:manage"
AUDIT_READ = "audit:read"
TOOLS_EXECUTE = "tools:execute"
TOOLS_EXECUTE_HIGH_RISK = "tools:execute_high_risk"
DATA_WRITE = "data:write"
DATA_READ = "data:read"

ALL_PERMISSIONS: frozenset[str] = frozenset(
    {
        ORG_MANAGE,
        MEMBERS_MANAGE,
        APIKEYS_MANAGE,
        AUDIT_READ,
        TOOLS_EXECUTE,
        TOOLS_EXECUTE_HIGH_RISK,
        DATA_WRITE,
        DATA_READ,
    }
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": ALL_PERMISSIONS,
    "admin": ALL_PERMISSIONS - {ORG_MANAGE},
    "member": frozenset({TOOLS_EXECUTE, DATA_WRITE, DATA_READ}),
    "viewer": frozenset({DATA_READ}),
}


def permissions_for(role: str | None) -> frozenset[str]:
    return ROLE_PERMISSIONS.get(role or "", frozenset())
