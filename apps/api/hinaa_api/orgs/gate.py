"""RBAC enforcement: `require_permission` dependency and the tool-execution check."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, Request

from ..config import Settings
from ..errors import HinaaError
from ..persistence.auth import AuthContext, reached_through_edge, resolve_auth
from . import service
from .permissions import TOOLS_EXECUTE, TOOLS_EXECUTE_HIGH_RISK


class OrgGate:
    def __init__(self, settings: Settings, memory: Any, conversation_auth: Callable[..., Any]) -> None:
        self.settings = settings
        self.memory = memory
        self.conversation_auth = conversation_auth

    def factory(self):  # type: ignore[no-untyped-def]
        return service.factory_of(self.settings, self.memory)

    def audit(self, auth: AuthContext, request: Request | None, action: str, target: str, outcome: str) -> None:
        if not auth.org_id:
            return
        client = getattr(request, "client", None)
        service.audit_record(
            self.factory(),
            auth.org_id,
            auth.user_id,
            action,
            target,
            outcome,
            ip=client.host if client else None,
            settings=self.settings,
        )

    def enforce(
        self, auth: AuthContext | None, request: Request | None, *permissions: str, target: str = ""
    ) -> AuthContext:
        if auth is None:
            raise HinaaError("AUTH_REQUIRED", "Organisation features need persistence and a signed-in user.", 401, True)
        missing = [p for p in permissions if p not in auth.permissions]
        if missing:
            self.audit(auth, request, "permission.denied", target or ",".join(missing), "denied")
            raise HinaaError(
                "PERMISSION_DENIED",
                f"Your role ({auth.role or 'none'}) does not allow this action ({', '.join(missing)}).",
                403,
            )
        return auth

    def require_permission(self, *permissions: str) -> Callable[..., Any]:
        gate = self

        async def dependency(request: Request, auth: AuthContext | None = Depends(self.conversation_auth)) -> AuthContext:
            return gate.enforce(auth, request, *permissions, target=f"{request.method} {request.url.path}")

        return dependency

    def authorize_tool(self, request: Request, tool_name: str) -> None:
        """RBAC for /tools/execute. Callers with no usable identity keep the legacy Host-based policy."""
        from ..tools import policy

        if self.memory is None:
            return
        try:
            auth = resolve_auth(
                request,
                self.settings,
                self.memory,
                authorization=request.headers.get("Authorization"),
                x_hinaa_dev_user=request.headers.get("X-HINAA-Dev-User"),
                allow_default_subject=self.settings.allow_tunnel_dev_auth or not reached_through_edge(request),
            )
        except HinaaError as error:
            # No usable identity: the endpoint has never required one, so the Host policy decides as before.
            if error.code == "AUTH_REQUIRED":
                return
            raise
        high_risk = tool_name in policy.IRREVERSIBLE_EXTERNAL_TOOLS
        needed = (TOOLS_EXECUTE, TOOLS_EXECUTE_HIGH_RISK) if high_risk else (TOOLS_EXECUTE,)
        self.enforce(auth, request, *needed, target=f"tool:{tool_name}")
        if high_risk or tool_name in policy.LOCAL_EFFECT_TOOLS:
            self.audit(auth, request, "tool.execute", f"tool:{tool_name}", "allowed")
