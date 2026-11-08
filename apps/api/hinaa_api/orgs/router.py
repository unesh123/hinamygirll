"""REST surface for organisations, members, API keys and the audit log (/v1/org)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..persistence.auth import AuthContext
from . import service
from .gate import OrgGate
from .permissions import APIKEYS_MANAGE, AUDIT_READ, DATA_READ, MEMBERS_MANAGE, ROLES, permissions_for


class MemberInvite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    userId: str = Field(min_length=1, max_length=64)
    role: str = "member"


class MemberPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(min_length=1)
    expiresInDays: int | None = Field(default=None, ge=1, le=3650)


def build_org_router(gate: OrgGate) -> APIRouter:
    router = APIRouter(tags=["Organisation"])
    settings = gate.settings

    @router.get("/me")
    async def me(auth: AuthContext = Depends(gate.require_permission(DATA_READ))) -> dict[str, Any]:
        orgs = service.memberships_of(gate.factory(), auth.user_id)
        return {
            "user": {"id": auth.user_id, "authSubject": auth.auth_subject},
            "org": next((o for o in orgs if o["id"] == auth.org_id), None),
            "role": auth.role,
            "permissions": sorted(auth.permissions),
            "authMode": auth.mode,
            "apiKeyId": auth.api_key_id,
            "organisations": orgs,
            "roles": list(ROLES),
            "rolePermissions": {r: sorted(permissions_for(r)) for r in ROLES},
        }

    @router.get("/members")
    async def members(auth: AuthContext = Depends(gate.require_permission(DATA_READ))) -> dict[str, Any]:
        return {"items": service.list_members(gate.factory(), str(auth.org_id))}

    @router.post("/members", status_code=201)
    async def invite(
        body: MemberInvite, request: Request, auth: AuthContext = Depends(gate.require_permission(MEMBERS_MANAGE))
    ) -> dict[str, Any]:
        member = service.add_member(gate.factory(), str(auth.org_id), str(auth.role), body.userId, body.role)
        gate.audit(auth, request, "member.add", f"user:{body.userId}:{body.role}", "success")
        return member

    @router.patch("/members/{user_id}")
    async def change_role(
        user_id: str,
        body: MemberPatch,
        request: Request,
        auth: AuthContext = Depends(gate.require_permission(MEMBERS_MANAGE)),
    ) -> dict[str, Any]:
        member = service.set_member_role(gate.factory(), str(auth.org_id), str(auth.role), user_id, body.role)
        gate.audit(auth, request, "member.role_change", f"user:{user_id}:{body.role}", "success")
        return member

    @router.delete("/members/{user_id}", status_code=204)
    async def remove(
        user_id: str, request: Request, auth: AuthContext = Depends(gate.require_permission(MEMBERS_MANAGE))
    ) -> None:
        service.remove_member(gate.factory(), str(auth.org_id), str(auth.role), user_id)
        gate.audit(auth, request, "member.remove", f"user:{user_id}", "success")

    @router.get("/api-keys")
    async def list_keys(auth: AuthContext = Depends(gate.require_permission(APIKEYS_MANAGE))) -> dict[str, Any]:
        return {"items": service.list_api_keys(gate.factory(), str(auth.org_id))}

    @router.post("/api-keys", status_code=201)
    async def create_key(
        body: ApiKeyCreate, request: Request, auth: AuthContext = Depends(gate.require_permission(APIKEYS_MANAGE))
    ) -> dict[str, Any]:
        created = service.create_api_key(
            gate.factory(),
            settings,
            str(auth.org_id),
            auth.user_id,
            auth.permissions,
            body.name,
            body.scopes,
            body.expiresInDays,
        )
        gate.audit(auth, request, "apikey.create", f"apikey:{created['id']}", "success")
        return created

    @router.delete("/api-keys/{key_id}")
    async def revoke_key(
        key_id: str, request: Request, auth: AuthContext = Depends(gate.require_permission(APIKEYS_MANAGE))
    ) -> dict[str, Any]:
        revoked = service.revoke_api_key(gate.factory(), str(auth.org_id), key_id)
        gate.audit(auth, request, "apikey.revoke", f"apikey:{key_id}", "success")
        return revoked

    @router.get("/audit")
    async def audit_list(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        action: str | None = None,
        user_id: str | None = Query(None, alias="userId"),
        outcome: str | None = None,
        auth: AuthContext = Depends(gate.require_permission(AUDIT_READ)),
    ) -> dict[str, Any]:
        return service.list_audit(
            gate.factory(), str(auth.org_id), limit=limit, offset=offset, action=action, user_id=user_id, outcome=outcome
        )

    @router.get("/audit/verify")
    async def audit_verify(auth: AuthContext = Depends(gate.require_permission(AUDIT_READ))) -> dict[str, Any]:
        return service.verify_audit(gate.factory(), str(auth.org_id))

    return router
