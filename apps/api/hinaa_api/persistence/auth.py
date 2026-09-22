from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass

from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import Header, Request

from ..config import Settings
from ..errors import HinaaError
from .memory_service import MemoryService


logger = logging.getLogger(__name__)

# Set by Cloudflare itself on every tunneled request, so a caller cannot remove
# or fake them without the edge overwriting the value.
_EDGE_MARKERS = ("cf-connecting-ip", "cf-ray", "cdn-loop")
# "testclient"/"testserver" are the hosts Starlette's TestClient dials.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]", "host.docker.internal", "testclient", "testserver"}


def _request_host(request: Request) -> str:
    host = (request.headers.get("host") or "").strip().lower()
    if host.startswith("["):
        return host.split("]")[0] + "]"
    if host.count(":") == 1 and host.rsplit(":", 1)[1].isdigit():
        return host.rsplit(":", 1)[0]
    return host


def reached_through_edge(request: Request) -> bool:
    """
    True when the request carries proof it came in over the public internet.

    cloudflared connects to this API from 127.0.0.1, so the peer address cannot
    tell his laptop from a stranger; the edge markers and the requested host can.
    Anything unrecognised counts as edge-facing, so a new proxy fails closed.
    """
    if any(request.headers.get(marker) for marker in _EDGE_MARKERS):
        return True
    host = _request_host(request)
    if not host:
        return True
    if host in _LOCAL_HOSTS:
        return False
    try:
        return not ipaddress.ip_address(host).is_private
    except ValueError:
        return True


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
    Dev/local mode: X-HINAA-Dev-User header when HINAA_AUTH_MODE=dev, and only
    for requests that never left this machine or his LAN.
    OIDC bearer is reserved; without a configured issuer, bearer is rejected.
    Clerk: verified via the official clerk_backend_api SDK, networkless with a
    CLERK_JWT_KEY PEM or against Clerk's published keys with CLERK_SECRET_KEY.
    Enforces HINAA_ALLOWED_USER_IDS single-owner gate if configured.
    """
    mode = settings.auth_mode
    if mode == "dev":
        # The dev header is a self-declared name and its expected value ships in
        # the browser bundle, so it can only be trusted on a request that never
        # left this machine or his LAN.
        if reached_through_edge(request):
            raise HinaaError(
                "AUTH_REQUIRED",
                "This HINAA instance is reachable from the internet, where the dev "
                "identity header is disabled. Sign in with a verified session.",
                401,
                True,
            )
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
        jwt_key = (settings.clerk_jwt_key or "").strip()
        secret_key = (
            settings.clerk_secret_key.get_secret_value().strip()
            if settings.clerk_secret_key
            else ""
        )
        if not jwt_key and not secret_key:
            raise HinaaError(
                "AUTH_NOT_CONFIGURED",
                "Clerk authentication needs CLERK_SECRET_KEY (or a CLERK_JWT_KEY PEM) on the API server.",
                503,
                False,
                True,
            )
        verify_options = {
            "jwt_key": jwt_key.replace("\\n", "\n") if jwt_key else None,
            "secret_key": secret_key or None,
            "authorized_parties": settings.clerk_authorized_parties or None,
        }
        try:
            state = Clerk().authenticate_request(
                request,
                AuthenticateRequestOptions(**verify_options),
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
            reason = str(getattr(state, "reason", None) or "no subject in token")
            logger.warning("Clerk rejected a session token: %s", reason)
            raise HinaaError(
                "AUTH_REQUIRED",
                "Sign in again to continue.",
                401,
                False,
                True,
                developer_message=reason,
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