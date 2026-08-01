from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, Request

from ..config import Settings
from ..errors import HinaaError
from .memory_service import MemoryService


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: str
    auth_subject: str
    mode: str


def resolve_auth(
    request: Request,
    settings: Settings,
    memory: MemoryService,
    authorization: str | None = None,
    x_hinaa_dev_user: str | None = None,
) -> AuthContext:
    """
    Dev/local mode: X-HINAA-Dev-User header when HINAA_AUTH_MODE=dev.
    OIDC bearer is reserved; without a configured issuer, bearer is rejected.
    """
    mode = settings.auth_mode
    if mode == "dev":
        subject = (x_hinaa_dev_user or settings.dev_auth_subject).strip()
        if not subject or len(subject) > 120:
            raise HinaaError("AUTH_REQUIRED", "Dev user identity is required.", 401, True)
        user = memory.ensure_user(subject)
        return AuthContext(user_id=user.id, auth_subject=subject, mode="dev")

    if mode == "oidc":
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HinaaError("AUTH_REQUIRED", "Sign in is required for private data.", 401, True)
        if not settings.oidc_issuer:
            raise HinaaError(
                "AUTH_NOT_CONFIGURED",
                "OIDC is selected but issuer is not configured.",
                503,
                True,
            )
        # Offline-safe scaffold: treat opaque local test tokens as subjects only in tests
        # when explicitly prefixed. Real JWT validation is deployment-gated.
        token = authorization.split(" ", 1)[1].strip()
        if settings.allow_oidc_scaffold_tokens and token.startswith("scaffold:"):
            subject = token.removeprefix("scaffold:")
            user = memory.ensure_user(subject)
            return AuthContext(user_id=user.id, auth_subject=subject, mode="oidc-scaffold")
        raise HinaaError(
            "AUTH_NOT_CONFIGURED",
            "Full OIDC token validation is not enabled in this offline build.",
            503,
            True,
        )

    raise HinaaError("AUTH_NOT_CONFIGURED", "Authentication mode is invalid.", 503, True)


def auth_dependency_factory(settings: Settings, memory: MemoryService):
    async def dependency(
        request: Request,
        authorization: str | None = Header(default=None),
        x_hinaa_dev_user: str | None = Header(default=None, alias="X-HINAA-Dev-User"),
    ) -> AuthContext:
        return resolve_auth(
            request,
            settings,
            memory,
            authorization=authorization,
            x_hinaa_dev_user=x_hinaa_dev_user,
        )

    return dependency
