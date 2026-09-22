"""Identity must not be claimable from the public internet.

The dev header is a literal shipped in the browser bundle, so these tests pin
the guard that refuses it on any request that arrived through an edge proxy.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from starlette.requests import Request

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.persistence.auth import resolve_auth
from hinaa_api.persistence.memory_service import MemoryService


def _request(host: str, extra_headers: dict[str, str] | None = None) -> Request:
    headers = [(b"host", host.encode())]
    headers += [(k.lower().encode(), v.encode()) for k, v in (extra_headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/v1/privacy/memories", "headers": headers})


def _memory() -> MagicMock:
    mock = MagicMock(spec=MemoryService)
    mock_user = MagicMock()
    mock_user.id = "user_owner_1"
    mock.ensure_user.return_value = mock_user
    return mock


def _dev_settings(**overrides) -> Settings:
    return Settings(HINAA_AUTH_MODE="dev", HINAA_ALLOWED_USER_IDS="", **overrides)


@pytest.mark.parametrize(
    ("host", "headers"),
    [
        ("same-regulation-crafts-aims.trycloudflare.com", {}),
        ("127.0.0.1:8000", {"cf-connecting-ip": "203.0.113.7"}),
        ("127.0.0.1:8000", {"cdn-loop": "cloudflare; loops=1"}),
        ("api.example.com", {}),
    ],
)
def test_dev_identity_is_refused_from_the_public_edge(host: str, headers: dict[str, str]) -> None:
    with pytest.raises(HinaaError) as caught:
        resolve_auth(
            _request(host, headers),
            _dev_settings(),
            _memory(),
            x_hinaa_dev_user="local-dev-user",
        )
    assert caught.value.status_code == 401
    assert caught.value.code == "AUTH_REQUIRED"


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:5173", "192.168.1.80:5173", "[::1]:8000"])
def test_dev_identity_still_works_locally(host: str) -> None:
    auth = resolve_auth(
        _request(host),
        _dev_settings(),
        _memory(),
        x_hinaa_dev_user="local-dev-user",
    )
    assert auth.auth_subject == "local-dev-user"
    assert auth.user_id == "user_owner_1"


def test_clerk_mode_verifies_with_only_a_secret_key() -> None:
    """A secret key is enough: the SDK fetches Clerk's published keys itself."""
    settings = Settings(
        HINAA_AUTH_MODE="clerk",
        CLERK_SECRET_KEY="sk_test_probe_value",
        CLERK_JWT_KEY=None,
    )
    with pytest.raises(HinaaError) as caught:
        resolve_auth(_request("hinaa-workspace.vercel.app"), settings, _memory())
    assert caught.value.code != "AUTH_NOT_CONFIGURED"
    assert caught.value.status_code == 401


def test_clerk_mode_reports_missing_credentials_as_not_configured() -> None:
    settings = Settings(HINAA_AUTH_MODE="clerk", CLERK_SECRET_KEY=None, CLERK_JWT_KEY=None)
    with pytest.raises(HinaaError) as caught:
        resolve_auth(_request("hinaa-workspace.vercel.app"), settings, _memory())
    assert caught.value.code == "AUTH_NOT_CONFIGURED"
