"""Fail closed before starting the production API; never log secret values."""
from __future__ import annotations

import os
from urllib.parse import urlparse


def _https_origin(value: str) -> bool:
    try:
        parsed = urlparse(value)
        valid_port = parsed.port is None or 1 <= parsed.port <= 65535
        return bool(parsed.scheme == "https" and parsed.hostname and valid_port and "*" not in value
                    and not parsed.username and not parsed.password and parsed.path in ("", "/")
                    and not parsed.query and not parsed.fragment)
    except ValueError:
        return False


def validate_environment(env: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if env.get("ENVIRONMENT") != "production":
        errors.append("ENVIRONMENT must be production")
    if env.get("HINAA_AUTH_MODE") != "clerk":
        errors.append("HINAA_AUTH_MODE must be clerk")
    if not env.get("CLERK_SECRET_KEY", "").startswith("sk_live_"):
        errors.append("CLERK_SECRET_KEY must belong to the production Clerk instance")
    if not env.get("HINAA_ALLOWED_USER_IDS", "").strip():
        errors.append("HINAA_ALLOWED_USER_IDS must identify the authorized owner")
    for name in ("CLERK_AUTHORIZED_PARTIES", "HINAA_ALLOWED_ORIGINS"):
        origins = [value.strip() for value in env.get(name, "").split(",") if value.strip()]
        if not origins or any(not _https_origin(origin) for origin in origins):
            errors.append(f"{name} must contain explicit HTTPS origins")
    for name in ("HINAA_ALLOW_REMOTE_LOCAL_TOOLS", "HINAA_ALLOW_TUNNEL_DEV_AUTH", "HINAA_ALLOW_OIDC_SCAFFOLD_TOKENS"):
        if env.get(name, "false").lower() not in ("false", "0"):
            errors.append(f"{name} must remain false")
    if env.get("HINAA_PERSISTENCE_ENABLED", "").lower() not in ("true", "1"):
        errors.append("HINAA_PERSISTENCE_ENABLED must be true")
    port = env.get("PORT", "8000")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        errors.append("PORT must be a valid TCP port")
    return errors


def main() -> None:
    errors = validate_environment(dict(os.environ))
    if errors:
        raise SystemExit("Production configuration refused:\n- " + "\n- ".join(errors))
    os.execvp("uvicorn", ["uvicorn", "hinaa_api.main:app", "--host", "0.0.0.0", "--port", os.environ.get("PORT", "8000")])


if __name__ == "__main__":
    main()
