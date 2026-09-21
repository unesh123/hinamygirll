from __future__ import annotations

from dataclasses import dataclass

from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
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
    *,
    allow_default_subject: bool = False,
) -> AuthContext:
    """
    Dev/local mode: X-HINAA-Dev-User header when HINAA_AUTH_MODE=dev.
    OIDC bearer is reserved; without a configured issuer, bearer is rejected.
    Clerk: verified via official clerk_backend_api SDK.
    Enforces HINAA_ALLOWED_USER_IDS single-owner gate if configured.
    """
    mode = settings.auth_mode
    if mode == "dev":
        subject = (x_hinaa_dev_user or "").strip()
        if not subject and allow_default_subject:
            subject = settings.dev_auth_subject.strip()
        # A network caller has to name itself. Falling back to the configured
        # subject made every anonymous request on the public URL the owner, and
        # this API is tunneled to the internet even while it runs in dev mode.
        if not subject or len(subject) > 120:
            raise HinaaError("AUTH_REQUIRED", "Dev user identity is required.", 401, True)
        if settings.hinaa_allowed_user_ids:
            allowed_ids = {u.strip() for u in settings.hinaa_allowed_user_ids.split(",") if u.strip()}
            if subject not in allowed_ids:
                raise HinaaError(
                    "USER_NOT_AUTHORIZED",
                    f"User '{subject}' is not authorized to access this private HINAA instance.",
                    status_code=403,
                )
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
        token = authorization.split(" ", 1)[1].strip()
        if settings.allow_oidc_scaffold_tokens and token.startswith("scaffold:"):
            subject = token.removeprefix("scaffold:")
            if settings.hinaa_allowed_user_ids:
                allowed_ids = {u.strip() for u in settings.hinaa_allowed_user_ids.split(",") if u.strip()}
                if subject not in allowed_ids:
                    raise HinaaError(
                        "USER_NOT_AUTHORIZED",
                        f"User '{subject}' is not authorized to access this private HINAA instance.",
                        status_code=403,
                    )
            user = memory.ensure_user(subject)
            return AuthContext(user_id=user.id, auth_subject=subject, mode="oidc-scaffold")
        raise HinaaError(
            "AUTH_NOT_CONFIGURED",
            "Full OIDC token validation is not enabled in this offline build.",
            503,
            True,
        )

    if mode == "clerk":
        if not settings.clerk_jwt_key:
            raise HinaaError(
                "AUTH_NOT_CONFIGURED",
                "Clerk authentication needs CLERK_JWT_KEY on the API server.",
                503,
                False,
                True,
            )
        try:
            state = Clerk().authenticate_request(
                request,
                AuthenticateRequestOptions(
                    jwt_key=settings.clerk_jwt_key.replace("\\n", "\n"),
                    authorized_parties=settings.clerk_authorized_parties or None,
                ),
            )
        except Exception as error:
            raise HinaaError(
                "AUTH_INVALID",
                "The sign-in token could not be verified.",
                401,
                False,
                True,
            ) from error
        payload = state.payload if state.is_signed_in else None
        subject = str((payload or {}).get("sub") or "").strip()
        if not subject or len(subject) > 160:
            raise HinaaError(
                "AUTH_REQUIRED",
                "Sign in again to continue.",
                401,
                False,
                True,
            )
        if settings.hinaa_allowed_user_ids:
            allowed_ids = {u.strip() for u in settings.hinaa_allowed_user_ids.split(",") if u.strip()}
            if subject not in allowed_ids:
                raise HinaaError(
                    "USER_NOT_AUTHORIZED",
                    f"User '{subject}' is not authorized to access this private HINAA instance.",
                    status_code=403,
                )
        user = memory.ensure_user(subject)
        return AuthContext(user_id=user.id, auth_subject=subject, mode="clerk")

    raise HinaaError("AUTH_NOT_CONFIGURED", f"Authentication mode is invalid: {mode!r}.", 503, True)


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